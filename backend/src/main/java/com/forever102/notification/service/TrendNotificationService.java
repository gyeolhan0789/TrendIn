package com.forever102.notification.service;

import com.forever102.notification.domain.Notification;
import com.forever102.notification.repository.NotificationRepository;
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

    @Transactional
    public int initializeExistingTrendStates() {
        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();
        Map<Long, Set<TrendType>> types = currentTypes(targets);
        targets.forEach(target -> target.interestKeyword()
                .updateTrendingState(!types.getOrDefault(
                        target.trend().getKeyword().getId(), Set.of()).isEmpty()));
        return targets.size();
    }

    @Transactional
    public int createNotificationsForTrendChanges() {
        Map<String, Notification> candidates = new LinkedHashMap<>();
        Instant detectedAt = clock.instant();

        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();
        Map<Long, Set<TrendType>> typesByKeyword = currentTypes(targets);
        for (TrendNotificationTarget target : targets) {
            List<TrendType> types = typesByKeyword.getOrDefault(
                            target.trend().getKeyword().getId(), Set.of()).stream()
                    .sorted(Comparator.comparing(Enum::name))
                    .toList();
            boolean trending = !types.isEmpty();
            boolean wasTrending = target.interestKeyword().isWasTrending();

            if (wasTrending && !trending) {
                target.interestKeyword().updateTrendingState(false);
                continue;
            }
            if (wasTrending || !trending) {
                continue;
            }

            String dedupKey = String.join(":", DEDUP_PREFIX,
                    target.interestKeyword().getId().toString(),
                    detectedAt.toString());
            String message = "관심 키워드 '%s'가 %s 트렌드에 포함되었어요."
                    .formatted(target.keyword(), displayNames(types));
            candidates.putIfAbsent(dedupKey, Notification.trendChange(
                    target.member(), target.trend(), message, dedupKey));
            target.interestKeyword().updateTrendingState(true);
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

    // 어느 기간에서든 트렌드로 진입하면 키워드 단위로 한 번 알린다. 오래된 구간은 제외한다.
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
