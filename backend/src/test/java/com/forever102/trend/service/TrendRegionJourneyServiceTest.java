package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository.CountryFirstDetection;
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
class TrendRegionJourneyServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock KeywordCountryDailyMetricRepository countryMetricRepository;
    TrendRegionJourneyService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new TrendRegionJourneyService(trendRepository, countryMetricRepository, clock);
    }

    @Test
    @DisplayName("최근 30일의 국가별 최초 관측일 순서와 한글 국가명을 반환한다")
    void returnsRegionJourney() {
        var trend = TrendFixture.trend();
        LocalDate start = LocalDate.of(2026, 8, 1);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository.findCountryFirstDetections(81L, start, end))
                .willReturn(List.of(
                        detection("FR", LocalDate.of(2026, 8, 3)),
                        detection("US", LocalDate.of(2026, 8, 7)),
                        detection("KR", LocalDate.of(2026, 8, 12))));

        var response = service.getJourney(101L);

        assertThat(response.period()).isEqualTo("30D");
        assertThat(response.startDate()).isEqualTo(start);
        assertThat(response.endDate()).isEqualTo(end);
        assertThat(response.regions())
                .extracting("countryCode", "countryName", "firstDetectedDate", "order")
                .containsExactly(
                        org.assertj.core.groups.Tuple.tuple("FR", "프랑스", LocalDate.of(2026, 8, 3), 1),
                        org.assertj.core.groups.Tuple.tuple("US", "미국", LocalDate.of(2026, 8, 7), 2),
                        org.assertj.core.groups.Tuple.tuple("KR", "대한민국", LocalDate.of(2026, 8, 12), 3));
        then(countryMetricRepository).should()
                .findCountryFirstDetections(81L, start, end);
    }

    @Test
    @DisplayName("최근 30일에 관측된 국가가 없으면 빈 목록을 반환한다")
    void returnsEmptyJourney() {
        var trend = TrendFixture.trend();
        LocalDate start = LocalDate.of(2026, 8, 1);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(countryMetricRepository.findCountryFirstDetections(81L, start, end))
                .willReturn(List.of());

        var response = service.getJourney(101L);

        assertThat(response.regions()).isEmpty();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 국가 지표를 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> service.getJourney(999L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(countryMetricRepository).shouldHaveNoInteractions();
    }

    private CountryFirstDetection detection(String countryCode, LocalDate firstDetectedDate) {
        return new CountryFirstDetection() {
            @Override
            public String getCountryCode() {
                return countryCode;
            }

            @Override
            public LocalDate getFirstDetectedDate() {
                return firstDetectedDate;
            }
        };
    }
}
