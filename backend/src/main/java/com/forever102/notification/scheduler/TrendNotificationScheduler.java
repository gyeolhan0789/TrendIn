package com.forever102.notification.scheduler;

import com.forever102.notification.service.TrendNotificationService;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class TrendNotificationScheduler {

    private final TrendNotificationService trendNotificationService;
    @Scheduled(
            cron = "${notification.trend-change.cron:0 0 0 * * *}",
            zone = "${notification.trend-change.zone:Asia/Seoul}")
    public void createTrendChangeNotifications() {
        trendNotificationService.initializeExistingTrendStates();
        trendNotificationService.createNotificationsForTrendChanges();
    }
}
