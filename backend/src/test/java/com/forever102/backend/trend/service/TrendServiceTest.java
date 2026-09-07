package com.forever102.backend.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.repository.TrendAiAnalysisRepository;
import com.forever102.backend.trend.repository.TrendAnalysisRepository;
import com.forever102.backend.trend.repository.TrendRepository;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TrendServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock TrendAnalysisRepository analysisRepository;
    @Mock TrendAiAnalysisRepository aiAnalysisRepository;
    @InjectMocks TrendService trendService;

    @Test
    @DisplayName("요청 기간의 최신 지표와 기간과 무관한 최신 AI 분석을 반환한다")
    void returnsRequestedPeriodAndLatestAiAnalysis() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(analysisRepository.findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(
                101L, "7D"))
                .willReturn(Optional.of(TrendFixture.analysis(trend, AnalysisPeriod.DAYS_7, 430, 123)));
        given(aiAnalysisRepository.findFirstByTrendIdOrderByGeneratedAtDescIdDesc(101L))
                .willReturn(Optional.of(TrendFixture.aiAnalysis(trend)));
        // when
        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7);
        // then
        assertThat(response.growthAmount()).isEqualTo(307);
        assertThat(response.analysisWindow().recentStart()).isEqualTo(TrendFixture.END.minusDays(7));
        assertThat(response.aiAnalysis().sourceContentIds()).containsExactly(301L, 302L);
    }

    @Test
    @DisplayName("요청 기간 지표가 없어도 기본 정보와 최신 AI 분석을 반환한다")
    void returnsBasicInfoAndAiWithoutPeriodAnalysis() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(analysisRepository.findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(
                101L, "30D")).willReturn(Optional.empty());
        given(aiAnalysisRepository.findFirstByTrendIdOrderByGeneratedAtDescIdDesc(101L))
                .willReturn(Optional.of(TrendFixture.aiAnalysis(trend)));
        // when
        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30);
        // then
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.trendType()).isNull();
        assertThat(response.mentionCount()).isNull();
        assertThat(response.growthRate()).isNull();
        assertThat(response.analysisWindow()).isNull();
        assertThat(response.evidence()).isNull();
        assertThat(response.aiAnalysis()).isNotNull();
    }

    @Test
    @DisplayName("AI 분석이 없으면 기간 지표를 유지하고 AI 결과만 null로 반환한다")
    void returnsPeriodAnalysisWithoutAi() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(analysisRepository.findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(
                101L, "24H"))
                .willReturn(Optional.of(TrendFixture.analysis(trend, AnalysisPeriod.HOURS_24, 10, 0)));
        given(aiAnalysisRepository.findFirstByTrendIdOrderByGeneratedAtDescIdDesc(101L))
                .willReturn(Optional.empty());
        // when
        var response = trendService.getTrendDetail(101L, AnalysisPeriod.HOURS_24);
        // then
        assertThat(response.mentionCount()).isEqualTo(10);
        assertThat(response.growthRate()).isNull();
        assertThat(response.aiAnalysis()).isNull();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 분석을 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        // given
        given(trendRepository.findById(101L)).willReturn(Optional.empty());
        // when & then
        assertThatThrownBy(() -> trendService.getTrendDetail(101L, AnalysisPeriod.HOURS_24))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(analysisRepository).shouldHaveNoInteractions();
        then(aiAnalysisRepository).shouldHaveNoInteractions();
    }
}
