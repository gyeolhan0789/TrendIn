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
import com.forever102.trend.domain.KeywordCountryDailyMetric;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TrendRegionHistoryServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock KeywordCountryDailyMetricRepository countryMetricRepository;
    TrendRegionHistoryService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new TrendRegionHistoryService(trendRepository, countryMetricRepository, clock);
    }

    @Test
    @DisplayName("최근 7일의 국가별 일 시계열을 빈 날짜는 0으로 채워 반환한다")
    void returnsDailyHistoryWithZeroFilledBuckets() {
        var trend = TrendFixture.trend();
        LocalDate start = LocalDate.of(2026, 8, 24);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository
                .findByKeywordIdAndCountryCodeAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        81L, "KR", start, end)).willReturn(List.of(
                        new KeywordCountryDailyMetric(trend.getKeyword(), "KR", start, 7),
                        new KeywordCountryDailyMetric(trend.getKeyword(), "KR", start.plusDays(2), 11)));

        var response = service.getHistory(101L, "kr", AnalysisPeriod.DAYS_7);

        assertThat(response.countryCode()).isEqualTo("KR");
        assertThat(response.countryName()).isEqualTo("대한민국");
        assertThat(response.history()).hasSize(7);
        assertThat(response.history()).extracting("mentionCount")
                .containsExactly(7L, 0L, 11L, 0L, 0L, 0L, 0L);
        assertThat(response.history().getFirst().bucketStart())
                .isEqualTo(TrendFixture.END.minusDays(7));
        assertThat(response.history().getFirst().bucketEnd())
                .isEqualTo(TrendFixture.END.minusDays(6));
    }

    @Test
    @DisplayName("최근 24시간은 완료된 하루 버킷 하나를 반환한다")
    void returnsSingleDailyBucketForTwentyFourHours() {
        var trend = TrendFixture.trend();
        LocalDate start = LocalDate.of(2026, 8, 30);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository
                .findByKeywordIdAndCountryCodeAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        81L, "US", start, end)).willReturn(List.of());

        var response = service.getHistory(101L, "US", AnalysisPeriod.HOURS_24);

        assertThat(response.history()).singleElement()
                .satisfies(point -> assertThat(point.mentionCount()).isZero());
    }

    @Test
    @DisplayName("국가 코드는 영문 두 자리가 아니면 거부한다")
    void rejectsInvalidCountryCode() {
        assertThatThrownBy(() -> service.getHistory(101L, "KOR", AnalysisPeriod.DAYS_7))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.VALIDATION_ERROR));
        then(trendRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("30일 국가 시계열 조회는 지원하지 않는다")
    void rejectsUnsupportedPeriod() {
        assertThatThrownBy(() -> service.getHistory(101L, "KR", AnalysisPeriod.DAYS_30))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.VALIDATION_ERROR));
        then(trendRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 국가 시계열을 조회하지 않는다")
    void rejectsMissingTrend() {
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getHistory(999L, "KR", AnalysisPeriod.DAYS_7))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(countryMetricRepository).shouldHaveNoInteractions();
    }
}
