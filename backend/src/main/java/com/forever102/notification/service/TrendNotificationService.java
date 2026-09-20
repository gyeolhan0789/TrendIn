package com.forever102.notification.service;

import com.forever102.notification.domain.Notification;
import com.forever102.notification.domain.NotificationSetting;
import com.forever102.notification.domain.NotificationType;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.notification.repository.NotificationSettingRepository;
import com.forever102.notification.repository.TrendNotificationTarget;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.repository.KeywordMetricRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class TrendNotificationService {

    private static final String DEDUP_PREFIX = "TREND_ENTRY";

    private final NotificationRepository notificationRepository;
    private final Clock clock;
    private final KeywordMetricRepository keywordMetricRepository;
    private final NotificationSettingRepository settingRepository;

    @Transactional
    public int initializeExistingTrendStates() {
        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();
        Map<Long, Set<TrendType>> types = currentTypes(targets);
        int initialized = 0;
        for (TrendNotificationTarget target : targets) {
            if (!target.interestKeyword().hasPreviousTrendState()) {
                target.interestKeyword().updateTrendState(sortedTypes(types.getOrDefault(
                        target.trend().getKeyword().getId(), Set.of())));
                initialized++;
            }
        }
        return initialized;
    }

    @Transactional
    public int createNotificationsForTrendChanges() {
        Map<String, Notification> candidates = new LinkedHashMap<>();
        Instant detectedAt = clock.instant();

        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();
        Map<Long, Set<TrendType>> typesByKeyword = currentTypes(targets);
        Map<Long, NotificationSetting> settingsByMember = settingRepository.findAllByMemberIdIn(
                        targets.stream().map(target -> target.member().getId()).distinct().toList())
                .stream().collect(Collectors.toMap(setting -> setting.getMember().getId(), setting -> setting));
        for (TrendNotificationTarget target : targets) {
            List<TrendType> currentTypes = sortedTypes(typesByKeyword.getOrDefault(
                    target.trend().getKeyword().getId(), Set.of()));
            if (!target.interestKeyword().hasPreviousTrendState()) {
                target.interestKeyword().updateTrendState(currentTypes);
                continue;
            }

            Set<TrendType> previous = EnumSet.noneOf(TrendType.class);
            previous.addAll(target.interestKeyword().getPreviousTrendTypes());
            Set<TrendType> current = EnumSet.noneOf(TrendType.class);
            current.addAll(currentTypes);
            NotificationSetting setting = settingsByMember.get(target.member().getId());

            if (!previous.contains(TrendType.RISING) && current.contains(TrendType.RISING)) {
                addCandidate(candidates, target, setting, NotificationType.KEYWORD_SURGE,
                        "관심 키워드 '%s'가 급등했어요.".formatted(target.keyword()), detectedAt);
            }
            if (!previous.isEmpty() && current.isEmpty()) {
                addCandidate(candidates, target, setting, NotificationType.KEYWORD_DROP,
                        "관심 키워드 '%s'가 트렌드에서 급락했어요.".formatted(target.keyword()), detectedAt);
            }
            if (!previous.contains(TrendType.NEW) && current.contains(TrendType.NEW)) {
                addCandidate(candidates, target, setting, NotificationType.NEW_TREND,
                        "관심 키워드 '%s'가 신규 트렌드로 발견되었어요.".formatted(target.keyword()), detectedAt);
            }
            if (!previous.isEmpty() && !current.isEmpty() && !previous.equals(current)) {
                addCandidate(candidates, target, setting, NotificationType.TREND_TURNING_POINT,
                        "관심 키워드 '%s'의 트렌드 유형이 %s에서 %s로 바뀌었어요."
                                .formatted(target.keyword(), displayNames(sortedTypes(previous)),
                                        displayNames(currentTypes)), detectedAt);
            }
            target.interestKeyword().updateTrendState(currentTypes);
        }

        if (candidates.isEmpty()) {
            return 0;
        }

        Set<String> existingKeys = Set.copyOf(
                notificationRepository.findExistingDedupKeys(candidates.keySet()));
        List<Notification> newNotifications = candidates.entrySet().stream()
                .filter(entry -> !existingKeys.contains(entry.getKey()))
                .map(Map.Entry::getValue)
                .toList();
        if (newNotifications.isEmpty()) {
            return 0;
        }
        notificationRepository.saveAll(newNotifications);
        return newNotifications.size();
    }

    private void addCandidate(Map<String, Notification> candidates, TrendNotificationTarget target,
            NotificationSetting setting, NotificationType type, String message, Instant detectedAt) {
        if (setting != null && !setting.isEnabled(type)) {
            return;
        }
        String dedupKey = String.join(":", DEDUP_PREFIX, type.name(),
                target.interestKeyword().getId().toString(), detectedAt.toString());
        candidates.putIfAbsent(dedupKey, Notification.trendEvent(
                target.member(), target.trend(), type, message, dedupKey));
    }

    private List<TrendType> sortedTypes(Set<TrendType> types) {
        return types.stream().sorted(Comparator.comparing(Enum::name)).toList();
    }

    // 완료된 최신 구간만 읽고, 기간별 유형은 키워드 단위 합집합으로 비교한다.
    private Map<Long, Set<TrendType>> currentTypes(List<TrendNotificationTarget> targets) {
        Map<Long, Set<TrendType>> result = new HashMap<>();
        if (targets.isEmpty()) {
            return result;
        }
        List<Long> keywordIds = targets.stream()
                .map(target -> target.trend().getKeyword().getId()).distinct().toList();
        Clock snapshot = Clock.fixed(clock.instant(), ZoneOffset.UTC);
        for (AnalysisPeriod period : AnalysisPeriod.values()) {
            AnalysisWindow window = AnalysisWindow.completed(period, snapshot);
            keywordMetricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                    keywordIds, period, window.getRecentStart(), window.getRecentEnd())
                    .forEach(metric -> result.computeIfAbsent(metric.getKeyword().getId(),
                            id -> EnumSet.noneOf(TrendType.class)).addAll(metric.getTrendTypes()));
        }
        return result;
    }

    private String displayNames(List<TrendType> types) {
        return types.stream()
                .map(type -> switch (type) {
                    case CURRENT -> "Top5";
                    case NEW -> "신규";
                    case RISING -> "급상승";
                })
                .collect(Collectors.joining(", "));
    }
}
