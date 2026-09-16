package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.Content;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordRelation;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.ContentRepository;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.KeywordRelationRepository;
import com.forever102.trend.repository.TrendRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

@ExtendWith(MockitoExtension.class)
class TrendServiceTest {

    @Mock TrendRepository trendRepository;
    @Mock KeywordMetricRepository metricRepository;
    @Mock ContentRepository contentRepository;
    @Mock KeywordRelationRepository keywordRelationRepository;
    TrendService trendService;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), ZoneId.of("UTC"));
        trendService = new TrendService(
                trendRepository, metricRepository, contentRepository, keywordRelationRepository, clock);
    }

    @Test
    @DisplayName("분야와 복수 트렌드 유형 및 완료 구간으로 목록을 조회한다")
    void returnsTrendList() {
        // given
        Trend trend = TrendFixture.trend();
        var metric = TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123);
        var pageable = PageRequest.of(0, 20);
        given(metricRepository.findRisingTrendPage("FASHION", "7D",
                TrendFixture.END.minusDays(7), TrendFixture.END, pageable))
                .willReturn(new PageImpl<>(List.of(metric), pageable, 1));
        given(trendRepository.findByKeywordIdIn(List.of(81L))).willReturn(List.of(trend));

        // when
        var response = trendService.getTrends(
                Domain.FASHION, TrendType.RISING, AnalysisPeriod.DAYS_7, 0, 20);

        // then
        assertThat(response.content()).hasSize(1);
        assertThat(response.content().getFirst().trendTypes()).containsExactly(TrendType.RISING);
        assertThat(response.content().getFirst().rank()).isEqualTo(1);
        assertThat(response.content().getFirst().mentionCount()).isEqualTo(430);
        assertThat(response.analysisWindow().recentStart()).isEqualTo(TrendFixture.END.minusDays(7));
    }

    @Test
    @DisplayName("목록 지표가 없으면 트렌드를 추가 조회하지 않고 빈 페이지를 반환한다")
    void returnsEmptyListWithoutTrendLookup() {
        // given
        var pageable = PageRequest.of(0, 20);
        given(metricRepository.findCurrentTrendPage("DEVELOP", "24H",
                TrendFixture.END.minusDays(1), TrendFixture.END, pageable))
                .willReturn(Page.empty(pageable));

        // when
        var response = trendService.getTrends(
                Domain.DEVELOP, TrendType.CURRENT, AnalysisPeriod.HOURS_24, 0, 20);

        // then
        assertThat(response.content()).isEmpty();
        then(trendRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("트렌드 키워드의 요청 기간 지표와 트렌드 상세 정보를 반환한다")
    void returnsRequestedKeywordMetric() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(metricRepository.findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                81L, AnalysisPeriod.DAYS_7, TrendFixture.END.minusDays(7), TrendFixture.END))
                .willReturn(Optional.of(TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123)));

        // when
        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7);

        // then
        assertThat(response.trendTypes()).containsExactly(TrendType.RISING);
        assertThat(response.growthAmount()).isEqualTo(307);
        assertThat(response.analysisWindow().recentStart()).isEqualTo(TrendFixture.END.minusDays(7));
        assertThat(response.summary()).contains("발레 스타일");
        assertThat(response.reason()).contains("신제품 출시");
    }

    @Test
    @DisplayName("요청 기간 지표가 없으면 트렌드 유형은 비고 기본 정보와 요약은 반환한다")
    void returnsBasicInfoWithoutPeriodMetric() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(metricRepository.findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                81L, AnalysisPeriod.DAYS_30,
                TrendFixture.END.minusDays(30), TrendFixture.END)).willReturn(Optional.empty());

        // when
        var response = trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30);

        // then
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.trendTypes()).isEmpty();
        assertThat(response.mentionCount()).isNull();
        assertThat(response.growthRate()).isNull();
        assertThat(response.analysisWindow()).isNull();
        assertThat(response.summary()).isNotBlank();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 지표를 조회하지 않고 404 예외를 발생시킨다")
    void rejectsMissingTrend() {
        // given
        given(trendRepository.findById(101L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> trendService.getTrendDetail(101L, AnalysisPeriod.HOURS_24))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(metricRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("트렌드 키워드에 연결된 콘텐츠 페이지를 반환한다")
    void returnsRelatedContents() {
        // given
        Trend trend = TrendFixture.trend();
        Content content = new Content("발레코어 스니커즈", "Vogue Korea",
                "https://example.com/articles/1", "curated/fashion/1.parquet",
                TrendFixture.END.minusHours(2), TrendFixture.END.minusHours(1));
        org.springframework.test.util.ReflectionTestUtils.setField(content, "id", 301L);
        var pageable = PageRequest.of(0, 20);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(contentRepository.findByKeywordId(81L, pageable))
                .willReturn(new PageImpl<>(List.of(content), pageable, 1));

        // when
        var response = trendService.getTrendContents(101L, 0, 20);

        // then
        assertThat(response.content()).hasSize(1);
        assertThat(response.content().getFirst().contentId()).isEqualTo(301L);
        assertThat(response.content().getFirst().source()).isEqualTo("Vogue Korea");
        assertThat(response.hasNext()).isFalse();
    }

    @Test
    @DisplayName("관련 콘텐츠가 없으면 빈 페이지를 반환한다")
    void returnsEmptyRelatedContents() {
        // given
        Trend trend = TrendFixture.trend();
        var pageable = PageRequest.of(0, 20);
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(contentRepository.findByKeywordId(81L, pageable)).willReturn(Page.empty(pageable));

        // when
        var response = trendService.getTrendContents(101L, 0, 20);

        // then
        assertThat(response.content()).isEmpty();
        assertThat(response.hasNext()).isFalse();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드의 콘텐츠를 요청하면 조회 없이 404 예외를 발생시킨다")
    void rejectsContentsForMissingTrend() {
        // given
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> trendService.getTrendContents(999L, 0, 20))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(contentRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("트렌드 키워드의 연관 키워드와 관계 점수를 반환한다")
    void returnsRelatedKeywords() {
        // given
        Trend trend = TrendFixture.trend();
        Keyword relatedKeyword = new Keyword("Mary Jane Sneakers", Domain.FASHION);
        org.springframework.test.util.ReflectionTestUtils.setField(relatedKeyword, "id", 82L);
        KeywordRelation relation = new KeywordRelation(trend.getKeyword(), relatedKeyword,
                new BigDecimal("87.50"), 25L,
                OffsetDateTime.parse("2026-08-31T08:00:00+09:00"));
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(keywordRelationRepository.findBySourceKeywordIdOrderByScore(81L))
                .willReturn(List.of(relation));

        // when
        var response = trendService.getRelatedKeywords(101L);

        // then
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.relatedKeywords()).hasSize(1);
        assertThat(response.relatedKeywords().getFirst().keywordId()).isEqualTo(82L);
        assertThat(response.relatedKeywords().getFirst().keyword()).isEqualTo("Mary Jane Sneakers");
        assertThat(response.relatedKeywords().getFirst().relationScore())
                .isEqualByComparingTo("87.50");
    }

    @Test
    @DisplayName("연관 키워드가 없으면 빈 목록을 반환한다")
    void returnsEmptyRelatedKeywords() {
        // given
        Trend trend = TrendFixture.trend();
        given(trendRepository.findById(101L)).willReturn(Optional.of(trend));
        given(keywordRelationRepository.findBySourceKeywordIdOrderByScore(81L))
                .willReturn(List.of());

        // when
        var response = trendService.getRelatedKeywords(101L);

        // then
        assertThat(response.relatedKeywords()).isEmpty();
    }

    @Test
    @DisplayName("존재하지 않는 트렌드의 연관 키워드를 요청하면 조회 없이 404 예외를 발생시킨다")
    void rejectsRelatedKeywordsForMissingTrend() {
        // given
        given(trendRepository.findById(999L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> trendService.getRelatedKeywords(999L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.TREND_NOT_FOUND));
        then(keywordRelationRepository).shouldHaveNoInteractions();
    }
}
