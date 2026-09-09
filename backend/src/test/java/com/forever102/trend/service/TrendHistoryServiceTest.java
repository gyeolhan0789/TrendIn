package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetricHistory;
import com.forever102.trend.repository.KeywordMetricHistoryRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TrendHistoryServiceTest {

    private static final OffsetDateTime END = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
    @Mock TrendRepository trendRepository;
    @Mock KeywordMetricHistoryRepository historyRepository;
    TrendHistoryService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new TrendHistoryService(trendRepository, historyRepository, clock);
    }

    @ParameterizedTest
    @EnumSource(AnalysisPeriod.class)
    @DisplayName("24H 1시간, 7D 1일, 30D 3일 단위 완료 구간을 반환한다")
    void returnsCompletedBuckets(AnalysisPeriod period) {
        // given
        var trend = TrendFixture.trend();
        var start = END.minus(period.getDuration());
        var sourceEnd = start.plusHours(1);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(historyRepository.findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                81L, start, END)).willReturn(List.of(
                        new KeywordMetricHistory(trend.getKeyword(), start, sourceEnd, 7L)));

        // when
        var response = service.getHistory(101L, period);

        // then
        int expectedSize = switch (period) {
            case HOURS_24 -> 24;
            case DAYS_7 -> 7;
            case DAYS_30 -> 10;
        };
        assertThat(response.history()).hasSize(expectedSize);
        assertThat(response.history().getFirst().bucketStart()).isEqualTo(start);
        assertThat(response.history().getFirst().bucketEnd())
                .isEqualTo(start.plus(period.getHistoryBucketDuration()));
        assertThat(response.history().getFirst().mentionCount()).isEqualTo(7L);
        assertThat(response.history().get(1).mentionCount()).isZero();
    }

    @Test
    @DisplayName("30D 조회는 세 시간 데이터가 아니라 3일 범위의 언급량을 합산한다")
    void aggregatesThirtyDaysByThreeDays() {
        // given
        var trend = TrendFixture.trend();
        var start = END.minusDays(30);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(historyRepository.findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                81L, start, END)).willReturn(List.of(
                        new KeywordMetricHistory(trend.getKeyword(), start, start.plusDays(1), 10L),
                        new KeywordMetricHistory(trend.getKeyword(), start.plusDays(1), start.plusDays(2), 20L),
                        new KeywordMetricHistory(trend.getKeyword(), start.plusDays(3), start.plusDays(4), 40L)));

        // when
        var response = service.getHistory(101L, AnalysisPeriod.DAYS_30);

        // then
        assertThat(response.history()).hasSize(10);
        assertThat(response.history().get(0).mentionCount()).isEqualTo(30L);
        assertThat(response.history().get(1).mentionCount()).isEqualTo(40L);
    }

    @Test
    @DisplayName("조회 구간에 저장된 행이 없으면 전체 버킷의 언급량을 0으로 반환한다")
    void fillsEmptyBucketsWithZero() {
        // given
        var trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(historyRepository.findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                81L, END.minusDays(7), END)).willReturn(List.of());

        // when
        var response = service.getHistory(101L, AnalysisPeriod.DAYS_7);

        // then
        assertThat(response.history()).hasSize(7);
        assertThat(response.history()).allSatisfy(point -> assertThat(point.mentionCount()).isZero());
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 시계열을 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        // given
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> service.getHistory(999L, AnalysisPeriod.HOURS_24))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(historyRepository).shouldHaveNoInteractions();
    }
}
