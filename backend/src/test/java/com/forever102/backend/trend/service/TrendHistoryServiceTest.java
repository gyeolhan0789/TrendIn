package com.forever102.backend.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.domain.HistoryBucketUnit;
import com.forever102.backend.trend.domain.TrendHistoryPoint;
import com.forever102.backend.trend.repository.TrendHistoryPointRepository;
import com.forever102.backend.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.junit.jupiter.api.extension.ExtendWith;

@ExtendWith(MockitoExtension.class)
class TrendHistoryServiceTest {

    private static final OffsetDateTime END = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
    @Mock TrendRepository trendRepository;
    @Mock TrendHistoryPointRepository historyPointRepository;
    TrendHistoryService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new TrendHistoryService(trendRepository, historyPointRepository, clock);
    }

    @ParameterizedTest
    @EnumSource(AnalysisPeriod.class)
    @DisplayName("24H는 시간 단위, 7D와 30D는 일 단위의 완료 구간을 오름차순으로 채운다")
    void returnsCompletedBuckets(AnalysisPeriod period) {
        var trend = TrendFixture.trend();
        var start = END.minus(period.getDuration());
        var unit = period.getHistoryBucketUnit();
        given(trendRepository.existsById(101L)).willReturn(true);
        given(historyPointRepository
                .findByTrendIdAndBucketUnitAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        101L, unit, start, END))
                .willReturn(List.of(new TrendHistoryPoint(trend, unit, start, 0L),
                        new TrendHistoryPoint(trend, unit,
                                period == AnalysisPeriod.HOURS_24 ? start.plusHours(2) : start.plusDays(2), 7L)));

        var response = service.getHistory(101L, period);

        int expectedSize = period == AnalysisPeriod.HOURS_24 ? 24 : (int) period.getDuration().toDays();
        assertThat(response.startAt()).isEqualTo(start);
        assertThat(response.endAt()).isEqualTo(END);
        assertThat(response.timezone()).isEqualTo("Asia/Seoul");
        assertThat(response.history()).hasSize(expectedSize).isSortedAccordingTo(
                java.util.Comparator.comparing(point -> point.timestamp().toInstant()));
        assertThat(response.history().get(0).mentionCount()).isZero();
        assertThat(response.history().get(1).mentionCount()).isZero();
        assertThat(response.history().get(2).mentionCount()).isEqualTo(7L);
    }

    @Test
    @DisplayName("조회 구간에 저장된 행이 없으면 NO_DATA와 빈 목록을 반환한다")
    void returnsNoData() {
        given(trendRepository.existsById(101L)).willReturn(true);
        given(historyPointRepository
                .findByTrendIdAndBucketUnitAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        101L, HistoryBucketUnit.DAY, END.minusDays(7), END)).willReturn(List.of());

        var response = service.getHistory(101L, AnalysisPeriod.DAYS_7);

        assertThat(response.dataStatus().name()).isEqualTo("NO_DATA");
        assertThat(response.history()).isEmpty();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 시계열을 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        given(trendRepository.existsById(999L)).willReturn(false);

        assertThatThrownBy(() -> service.getHistory(999L, AnalysisPeriod.HOURS_24))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(historyPointRepository).shouldHaveNoInteractions();
    }
}
