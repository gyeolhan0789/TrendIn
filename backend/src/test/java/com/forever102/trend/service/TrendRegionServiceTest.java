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
class TrendRegionServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock KeywordCountryDailyMetricRepository countryMetricRepository;
    TrendRegionService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new TrendRegionService(trendRepository, countryMetricRepository, clock);
    }

    @Test
    @DisplayName("최근 7일 국가별 언급량을 합산해 순위와 한글 국가명을 반환한다")
    void returnsRankedRegions() {
        var trend = TrendFixture.trend();
        var keyword = trend.getKeyword();
        LocalDate start = LocalDate.of(2026, 8, 24);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository
                .findByKeywordIdAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        81L, start, end)).willReturn(List.of(
                        new KeywordCountryDailyMetric(keyword, "KR", start, 4),
                        new KeywordCountryDailyMetric(keyword, "US", start, 10),
                        new KeywordCountryDailyMetric(keyword, "KR", start.plusDays(1), 6),
                        new KeywordCountryDailyMetric(keyword, "FR", start.plusDays(1), 10)));

        var response = service.getRegions(101L, AnalysisPeriod.DAYS_7);

        assertThat(response.period()).isEqualTo("7D");
        assertThat(response.startDate()).isEqualTo(start);
        assertThat(response.endDate()).isEqualTo(end);
        assertThat(response.regions()).extracting("countryCode", "countryName", "mentionCount", "rank")
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple("FR", "프랑스", 10L, 1),
                        org.assertj.core.groups.Tuple.tuple("KR", "대한민국", 10L, 1),
                        org.assertj.core.groups.Tuple.tuple("US", "미국", 10L, 1));
    }

    @Test
    @DisplayName("국가별 지표가 없으면 빈 순위를 반환한다")
    void returnsEmptyRegions() {
        var trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository
                .findByKeywordIdAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        81L, LocalDate.of(2026, 8, 30), LocalDate.of(2026, 8, 31)))
                .willReturn(List.of());

        var response = service.getRegions(101L, AnalysisPeriod.HOURS_24);

        assertThat(response.regions()).isEmpty();
    }

    @Test
    @DisplayName("30일 국가 순위 조회는 지원하지 않는다")
    void rejectsUnsupportedPeriod() {
        assertThatThrownBy(() -> service.getRegions(101L, AnalysisPeriod.DAYS_30))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.VALIDATION_ERROR));
        then(trendRepository).shouldHaveNoInteractions();
        then(countryMetricRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 국가 지표를 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getRegions(999L, AnalysisPeriod.DAYS_7))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(countryMetricRepository).shouldHaveNoInteractions();
    }
}
