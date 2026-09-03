package com.forever102.backend.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.Keyword;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.dto.TrendDetailResponse;
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

    @Mock
    private TrendRepository trendRepository;
    @Mock
    private TrendAnalysisRepository analysisRepository;
    @InjectMocks
    private TrendService trendService;

    @Test
    @DisplayName("기본 설명과 AI 요약을 분리하고 저장된 최신 분석을 반환한다")
    void returnsDetailWithStoredAnalysis() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(101L))
                .willReturn(Optional.of(TrendFixture.analysis(trend, 430, 123)));
        // when
        TrendDetailResponse response = trendService.getTrendDetail(101L);
        // then
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.keywordId()).isEqualTo(81L);
        assertThat(response.keyword()).isEqualTo("Ballet Sneakers");
        assertThat(response.description()).isEqualTo(trend.getDescription());
        assertThat(response.domain()).isEqualTo(new TrendDetailResponse.DomainResponse(Domain.FASHION, "패션"));
        assertThat(response.growthAmount()).isEqualTo(307);
        assertThat(response.growthRate()).isEqualByComparingTo("249.6");
        assertThat(response.aiAnalysis().summary()).isNotEqualTo(response.description());
        assertThat(response.aiAnalysis().sourceContentIds()).containsExactly(301L, 302L);
        assertThat(response.evidence().ruleVersion()).isEqualTo("example-v1");
        assertThat(response.analysisWindow().recentStart()).isEqualTo(TrendFixture.END.minusDays(1));
    }

    @Test
    @DisplayName("24H 분석이 없으면 기본 정보를 유지하고 분석 필드를 null로 반환한다")
    void returnsBasicInfoWithoutAnalysis() {
        // given
        given(trendRepository.findById(101L)).willReturn(Optional.of(TrendFixture.trend()));
        given(analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(101L)).willReturn(Optional.empty());
        // when
        TrendDetailResponse response = trendService.getTrendDetail(101L);
        // then
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.description()).isNotBlank();
        assertThat(response.trendType()).isNull();
        assertThat(response.mentionCount()).isNull();
        assertThat(response.previousMentionCount()).isNull();
        assertThat(response.growthAmount()).isNull();
        assertThat(response.growthRate()).isNull();
        assertThat(response.analysisWindow()).isNull();
        assertThat(response.analyzedAt()).isNull();
        assertThat(response.evidence()).isNull();
        assertThat(response.aiAnalysis()).isNull();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 404 비즈니스 예외를 발생시킨다")
    void rejectsMissingTrend() {
        // given
        given(trendRepository.findById(101L)).willReturn(Optional.empty());
        // when & then
        assertThatThrownBy(() -> trendService.getTrendDetail(101L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(analysisRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("개발 분야는 기존 DEVELOP Enum과 개발 표시명으로 반환한다")
    void reusesDevelopDomain() {
        // given
        Trend trend = new Trend(new Keyword("Java", Domain.DEVELOP), "자바", TrendFixture.END);
        given(trendRepository.findById(1L)).willReturn(Optional.of(trend));
        given(analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(1L)).willReturn(Optional.empty());
        // when & then
        assertThat(trendService.getTrendDetail(1L).domain())
                .isEqualTo(new TrendDetailResponse.DomainResponse(Domain.DEVELOP, "개발"));
    }
}
