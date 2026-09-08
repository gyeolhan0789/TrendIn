package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TrendServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock KeywordMetricRepository metricRepository;
    TrendService trendService;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), ZoneId.of("UTC"));
        trendService = new TrendService(trendRepository, metricRepository, clock);
    }

    @Test
    @DisplayName("트렌드 키워드의 요청 기간 지표와 트렌드 상세 정보를 반환한다")
    void returnsRequestedKeywordMetric() {
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(metricRepository.findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                81L, AnalysisPeriod.DAYS_7, TrendFixture.END.minusDays(7), TrendFixture.END))
                .willReturn(Optional.of(TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123)));

        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7);

        assertThat(response.trendTypes()).containsExactly(com.forever102.trend.domain.TrendType.RISING);
        assertThat(response.growthAmount()).isEqualTo(307);
        assertThat(response.analysisWindow().recentStart()).isEqualTo(TrendFixture.END.minusDays(7));
        assertThat(response.summary()).contains("발레 스타일");
        assertThat(response.reason()).contains("신제품 출시");
    }

    @Test
    @DisplayName("요청 기간 지표가 없어도 트렌드 기본 정보와 요약을 반환한다")
    void returnsBasicInfoWithoutPeriodMetric() {
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(metricRepository.findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                81L, AnalysisPeriod.DAYS_30,
                TrendFixture.END.minusDays(30), TrendFixture.END)).willReturn(Optional.empty());

        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30);

        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.trendTypes()).containsExactly(com.forever102.trend.domain.TrendType.RISING);
        assertThat(response.mentionCount()).isNull();
        assertThat(response.growthRate()).isNull();
        assertThat(response.analysisWindow()).isNull();
        assertThat(response.summary()).isNotBlank();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 지표를 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        given(trendRepository.findById(101L)).willReturn(Optional.empty());

        assertThatThrownBy(() -> trendService.getTrendDetail(101L, AnalysisPeriod.HOURS_24))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(metricRepository).shouldHaveNoInteractions();
    }
}
