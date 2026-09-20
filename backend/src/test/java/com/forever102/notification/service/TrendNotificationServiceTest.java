package com.forever102.notification.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.domain.NotificationSetting;
import com.forever102.notification.domain.NotificationType;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.notification.repository.NotificationSettingRepository;
import com.forever102.notification.repository.TrendNotificationTarget;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.KeywordMetricRepository;
import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class TrendNotificationServiceTest {

    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-10T12:00:00+09:00");

    @Mock NotificationRepository notificationRepository;
    @Mock NotificationSettingRepository settingRepository;
    @Mock KeywordMetricRepository metricRepository;
    @Mock Clock clock;
    private TrendNotificationService service;

    @BeforeEach
    void setUp() {
        service = new TrendNotificationService(notificationRepository, clock,
                metricRepository, settingRepository);
        lenient().when(clock.instant()).thenReturn(NOW.toInstant());
    }

    @Test
    @DisplayName("RISING 유형에 새로 진입하면 키워드 급등 알림을 생성한다")
    void createsSurgeNotification() {
        TrendNotificationTarget target = target(List.of(TrendType.CURRENT),
                List.of(TrendType.CURRENT, TrendType.RISING));
        prepare(target);

        assertThat(service.createNotificationsForTrendChanges()).isEqualTo(2);
        assertThat(savedNotifications()).extracting(Notification::getNotificationType)
                .containsExactlyInAnyOrder(NotificationType.KEYWORD_SURGE,
                        NotificationType.TREND_TURNING_POINT);
    }

    @Test
    @DisplayName("기존 트렌드 유형이 모두 사라지면 키워드 급락 알림을 생성한다")
    void createsDropNotification() {
        TrendNotificationTarget target = target(List.of(TrendType.CURRENT), List.of());
        prepare(target);

        assertThat(service.createNotificationsForTrendChanges()).isOne();
        assertThat(savedNotifications().getFirst().getNotificationType())
                .isEqualTo(NotificationType.KEYWORD_DROP);
    }

    @Test
    @DisplayName("NEW 유형에 새로 진입하면 신규 트렌드 알림을 생성한다")
    void createsNewTrendNotification() {
        TrendNotificationTarget target = freshTarget(List.of(TrendType.NEW));
        prepare(target);

        assertThat(service.createNotificationsForTrendChanges()).isOne();
        assertThat(savedNotifications().getFirst().getNotificationType())
                .isEqualTo(NotificationType.NEW_TREND);
    }

    @Test
    @DisplayName("등록 후 처음 트렌드가 된 관심 키워드가 RISING이면 급등 알림을 생성한다")
    void createsSurgeNotificationOnFirstTrendEntry() {
        TrendNotificationTarget target = freshTarget(List.of(TrendType.RISING));
        prepare(target);

        assertThat(service.createNotificationsForTrendChanges()).isOne();
        assertThat(savedNotifications().getFirst().getNotificationType())
                .isEqualTo(NotificationType.KEYWORD_SURGE);
    }

    @Test
    @DisplayName("비어 있지 않은 기존 트렌드 유형이 변경되면 전환점 알림을 생성한다")
    void createsTurningPointNotification() {
        TrendNotificationTarget target = target(List.of(TrendType.CURRENT), List.of(TrendType.NEW));
        prepare(target);

        assertThat(service.createNotificationsForTrendChanges()).isEqualTo(2);
        assertThat(savedNotifications()).extracting(Notification::getNotificationType)
                .containsExactlyInAnyOrder(NotificationType.NEW_TREND,
                        NotificationType.TREND_TURNING_POINT);
    }

    @Test
    @DisplayName("사용자가 끈 유형의 알림은 생성하지 않고 이전 상태는 갱신한다")
    void skipsDisabledNotificationAndUpdatesState() {
        TrendNotificationTarget target = target(List.of(), List.of(TrendType.RISING));
        NotificationSetting setting = NotificationSetting.defaults(target.member());
        setting.update(false, true, true, true);
        prepare(target);
        given(settingRepository.findAllByMemberIdIn(anyCollection())).willReturn(List.of(setting));

        assertThat(service.createNotificationsForTrendChanges()).isZero();
        assertThat(target.interestKeyword().getPreviousTrendTypes())
                .containsExactly(TrendType.RISING);
        verify(notificationRepository, never()).saveAll(any());
    }

    @Test
    @DisplayName("이전 상태가 없는 관심 키워드는 현재 상태만 초기화하고 알리지 않는다")
    void initializesMissingStateWithoutNotification() {
        TrendNotificationTarget target = uninitializedTarget(List.of(TrendType.RISING));
        ReflectionTestUtils.setField(
                target.interestKeyword(), "previousTrendTypes", null);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));

        assertThat(service.initializeExistingTrendStates()).isOne();
        assertThat(target.interestKeyword().getPreviousTrendTypes())
                .containsExactly(TrendType.RISING);
        verify(notificationRepository, never()).saveAll(any());
    }

    private void prepare(TrendNotificationTarget target) {
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));
        lenient().when(notificationRepository.findExistingDedupKeys(anyCollection()))
                .thenReturn(List.of());
    }

    private TrendNotificationTarget target(List<TrendType> previous, List<TrendType> current) {
        TrendNotificationTarget target = uninitializedTarget(current);
        target.interestKeyword().updateTrendState(previous);
        return target;
    }

    private TrendNotificationTarget freshTarget(List<TrendType> current) {
        return uninitializedTarget(current);
    }

    private TrendNotificationTarget uninitializedTarget(List<TrendType> current) {
        Member member = Member.create("member@example.com", "password-hash", "회원");
        ReflectionTestUtils.setField(member, "id", 1L);
        Keyword keyword = new Keyword("발레코어", Domain.FASHION);
        ReflectionTestUtils.setField(keyword, "id", 81L);
        MemberInterestKeyword interestKeyword = MemberInterestKeyword.register(member, keyword);
        ReflectionTestUtils.setField(interestKeyword, "id", 100L);
        Trend trend = new Trend(keyword, NOW);
        ReflectionTestUtils.setField(trend, "id", 10L);
        KeywordMetric metric = KeywordMetric.builder().keyword(keyword).period(AnalysisPeriod.DAYS_7)
                .periodStart(NOW.minusDays(7)).periodEnd(NOW).trendTypes(current).build();
        given(metricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                anyCollection(), any(), any(), any())).willReturn(List.of(metric));
        return new TrendNotificationTarget(interestKeyword, member, trend, keyword.getName());
    }

    @SuppressWarnings("unchecked")
    private List<Notification> savedNotifications() {
        ArgumentCaptor<List<Notification>> captor = ArgumentCaptor.forClass(List.class);
        verify(notificationRepository).saveAll(captor.capture());
        return captor.getValue();
    }
}
