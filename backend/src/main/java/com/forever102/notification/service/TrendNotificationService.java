package com.forever102.notification.service;

import com.forever102.notification.domain.Notification;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.notification.repository.TrendNotificationTarget;
import com.forever102.trend.domain.TrendType;
import java.time.Clock;
import java.time.Instant;
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

    @Transactional
    public int initializeExistingTrendStates() {
        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();
        targets.forEach(target -> target.interestKeyword()
                .updateTrendingState(!target.trend().getTrendTypes().isEmpty()));
        return targets.size();
    }

    @Transactional
    public int createNotificationsForTrendChanges() {
        Map<String, Notification> candidates = new LinkedHashMap<>();
        Instant detectedAt = clock.instant();

        for (TrendNotificationTarget target : notificationRepository.findTrendNotificationTargets()) {
            List<TrendType> types = target.trend().getTrendTypes().stream()
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
