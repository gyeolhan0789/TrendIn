package com.forever102.notification.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.notification.repository.TrendNotificationTarget;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.AnalysisPeriod;
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

    private static final OffsetDateTime UPDATED_AT =
            OffsetDateTime.parse("2026-09-10T12:00:00+09:00");

    @Mock NotificationRepository notificationRepository;
    @Mock Clock clock;
    @Mock KeywordMetricRepository metricRepository;
    private KeywordMetric currentMetric;

    private TrendNotificationService service;

    @BeforeEach
    void setUp() {
        service = new TrendNotificationService(notificationRepository, clock, metricRepository);
        lenient().when(clock.instant()).thenReturn(UPDATED_AT.toInstant());
    }

    @Test
    @DisplayName("비트렌드 관심 키워드가 CURRENT에 진입하면 알림 한 개를 생성한다")
    void createsOneNotificationOnCurrentEntry() {
        // given
        TrendNotificationTarget target = target(false, List.of(TrendType.CURRENT), UPDATED_AT);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));
        given(notificationRepository.findExistingDedupKeys(anyCollection())).willReturn(List.of());
        given(clock.instant()).willReturn(UPDATED_AT.toInstant());

        // when
        int createdCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(createdCount).isOne();
        assertThat(target.interestKeyword().isWasTrending()).isTrue();
        assertThat(savedNotification()).satisfies(notification -> {
            assertThat(notification.getDedupKey())
                    .isEqualTo("TREND_ENTRY:100:2026-09-10T03:00:00Z");
            assertThat(notification.getMessage())
                    .isEqualTo("관심 키워드 '발레코어'가 Top5 트렌드에 포함되었어요.");
        });
    }

    @Test
    @DisplayName("여러 트렌드 유형에 동시에 진입해도 유형을 함께 표시한 알림 한 개를 생성한다")
    void createsOneNotificationForMultipleTypes() {
        // given
        TrendNotificationTarget target = target(false,
                List.of(TrendType.RISING, TrendType.CURRENT, TrendType.NEW), UPDATED_AT);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));
        given(notificationRepository.findExistingDedupKeys(anyCollection())).willReturn(List.of());
        given(clock.instant()).willReturn(UPDATED_AT.toInstant());

        // when
        int createdCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(createdCount).isOne();
        assertThat(savedNotification().getMessage())
                .isEqualTo("관심 키워드 '발레코어'가 Top5, 신규, 급상승 트렌드에 포함되었어요.");
    }

    @Test
    @DisplayName("30D 지표가 비어 있어도 24H의 NEW 판정으로 키워드 알림을 생성한다")
    void notifiesFromAnyRequestedPeriodMetric() {
        TrendNotificationTarget target = target(false, List.of(), UPDATED_AT);
        KeywordMetric dailyMetric = KeywordMetric.builder().keyword(target.trend().getKeyword())
                .period(AnalysisPeriod.HOURS_24).periodStart(UPDATED_AT.minusDays(1))
                .periodEnd(UPDATED_AT).trendTypes(List.of(TrendType.NEW)).build();
        given(metricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                anyCollection(), eq(AnalysisPeriod.HOURS_24), any(), any()))
                .willReturn(List.of(dailyMetric));
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));
        given(notificationRepository.findExistingDedupKeys(anyCollection())).willReturn(List.of());

        assertThat(service.createNotificationsForTrendChanges()).isOne();
        assertThat(savedNotification().getMessage()).contains("신규 트렌드");
    }

    @Test
    @DisplayName("이미 트렌드인 관심 키워드의 유형 구성이 바뀌어도 추가 알림을 생성하지 않는다")
    void doesNotNotifyTypeCompositionChange() {
        // given
        TrendNotificationTarget target = target(true,
                List.of(TrendType.CURRENT, TrendType.RISING), UPDATED_AT);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));

        // when
        int createdCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(createdCount).isZero();
        assertThat(target.interestKeyword().isWasTrending()).isTrue();
        verify(notificationRepository, never()).saveAll(org.mockito.ArgumentMatchers.anyList());
    }

    @Test
    @DisplayName("트렌드에서 벗어난 관심 키워드는 알림 없이 비트렌드 상태로 기록한다")
    void recordsTrendExitWithoutNotification() {
        // given
        TrendNotificationTarget target = target(true, List.of(TrendType.CURRENT), UPDATED_AT);
        ReflectionTestUtils.setField(currentMetric, "trendTypes", new TrendType[0]);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));

        // when
        int createdCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(createdCount).isZero();
        assertThat(target.interestKeyword().isWasTrending()).isFalse();
    }

    @Test
    @DisplayName("비트렌드로 돌아간 관심 키워드가 다시 진입하면 새로운 알림을 생성한다")
    void notifiesReentryAfterTrendExit() {
        // given
        TrendNotificationTarget target = target(true, List.of(TrendType.CURRENT), UPDATED_AT);
        ReflectionTestUtils.setField(currentMetric, "trendTypes", new TrendType[0]);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));

        // when
        service.createNotificationsForTrendChanges();
        ReflectionTestUtils.setField(currentMetric, "trendTypes", new TrendType[]{TrendType.RISING});
        ReflectionTestUtils.setField(target.trend(), "updatedAt", UPDATED_AT.plusHours(1));
        given(notificationRepository.findExistingDedupKeys(anyCollection())).willReturn(List.of());
        given(clock.instant()).willReturn(UPDATED_AT.plusHours(1).toInstant());
        int createdCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(createdCount).isOne();
        assertThat(target.interestKeyword().isWasTrending()).isTrue();
        assertThat(savedNotification().getDedupKey())
                .isEqualTo("TREND_ENTRY:100:2026-09-10T04:00:00Z");
    }

    @Test
    @DisplayName("동일한 트렌드 진입 상태에서 반복 실행해도 알림은 한 번만 생성한다")
    void doesNotDuplicateNotificationOnRepeatedRun() {
        // given
        TrendNotificationTarget target = target(false, List.of(TrendType.NEW), UPDATED_AT);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));
        given(notificationRepository.findExistingDedupKeys(anyCollection())).willReturn(List.of());
        given(clock.instant()).willReturn(UPDATED_AT.toInstant());

        // when
        int firstCount = service.createNotificationsForTrendChanges();
        int secondCount = service.createNotificationsForTrendChanges();

        // then
        assertThat(firstCount).isOne();
        assertThat(secondCount).isZero();
        verify(notificationRepository, times(1)).saveAll(org.mockito.ArgumentMatchers.anyList());
    }

    @Test
    @DisplayName("최초 기준 상태 초기화는 기존 트렌드 관심 키워드의 상태만 기록한다")
    void initializesExistingStateWithoutNotification() {
        // given
        TrendNotificationTarget target = target(false, List.of(TrendType.RISING), UPDATED_AT);
        given(notificationRepository.findTrendNotificationTargets()).willReturn(List.of(target));

        // when
        int initializedCount = service.initializeExistingTrendStates();

        // then
        assertThat(initializedCount).isOne();
        assertThat(target.interestKeyword().isWasTrending()).isTrue();
        verify(notificationRepository, never()).saveAll(org.mockito.ArgumentMatchers.anyList());
    }

    @SuppressWarnings("unchecked")
    private Notification savedNotification() {
        ArgumentCaptor<List<Notification>> captor = ArgumentCaptor.forClass(List.class);
        verify(notificationRepository).saveAll(captor.capture());
        return captor.getValue().getFirst();
    }

    private TrendNotificationTarget target(
            boolean wasTrending, List<TrendType> types, OffsetDateTime updatedAt) {
        Member member = Member.create("member@example.com", "password-hash", "회원");
        ReflectionTestUtils.setField(member, "id", 1L);
        Keyword keyword = new Keyword("발레코어", Domain.FASHION);
        ReflectionTestUtils.setField(keyword, "id", 81L);
        MemberInterestKeyword interestKeyword = MemberInterestKeyword.register(member, keyword);
        ReflectionTestUtils.setField(interestKeyword, "id", 100L);
        interestKeyword.updateTrendingState(wasTrending);
        Trend trend = new Trend(keyword, updatedAt);
        currentMetric = KeywordMetric.builder().keyword(keyword).period(AnalysisPeriod.DAYS_7)
                .periodStart(updatedAt.minusDays(7)).periodEnd(updatedAt)
                .trendTypes(types).build();
        given(metricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                anyCollection(), any(), any(), any())).willReturn(List.of(currentMetric));
        ReflectionTestUtils.setField(trend, "id", 10L);
        return new TrendNotificationTarget(interestKeyword, member, trend, keyword.getName());
    }
}
