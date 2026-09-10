package com.forever102.notification.scheduler;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.inOrder;

import com.forever102.notification.service.TrendNotificationService;
import java.lang.reflect.Method;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.scheduling.annotation.Scheduled;

@ExtendWith(MockitoExtension.class)
class TrendNotificationSchedulerTest {

    @Mock TrendNotificationService trendNotificationService;
    @InjectMocks TrendNotificationScheduler scheduler;

    @Test
    @DisplayName("최초 실행은 기존 상태를 초기화하고 다음 실행부터 진입 알림을 생성한다")
    void initializesBeforeCreatingNotifications() {
        // given

        // when
        scheduler.createTrendChangeNotifications();
        scheduler.createTrendChangeNotifications();

        // then
        InOrder order = inOrder(trendNotificationService);
        order.verify(trendNotificationService).initializeExistingTrendStates();
        order.verify(trendNotificationService).createNotificationsForTrendChanges();
    }

    @Test
    @DisplayName("매일 자정에 Asia/Seoul 기준으로 실행하도록 설정한다")
    void configuresDailyMidnightInSeoul() throws NoSuchMethodException {
        // given
        Method method = TrendNotificationScheduler.class
                .getDeclaredMethod("createTrendChangeNotifications");

        // when
        Scheduled scheduled = method.getAnnotation(Scheduled.class);

        // then
        assertThat(scheduled.cron())
                .isEqualTo("${notification.trend-change.cron:0 0 0 * * *}");
        assertThat(scheduled.zone())
                .isEqualTo("${notification.trend-change.zone:Asia/Seoul}");
        assertThat(scheduled.fixedDelayString()).isEmpty();
    }
}
