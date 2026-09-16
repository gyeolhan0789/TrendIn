package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.member.domain.Domain;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.TrendRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class KeywordServiceTest {

    @Mock KeywordRepository keywordRepository;
    @Mock TrendRepository trendRepository;
    @Mock KeywordMetricRepository keywordMetricRepository;

    private KeywordService keywordService;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-30T15:00:00Z"),
                ZoneId.of("Asia/Seoul"));
        keywordService = new KeywordService(
                keywordRepository, trendRepository, keywordMetricRepository, clock);
    }

    @Test
    @DisplayName("검색 결과의 현재 트렌드 정보와 완료된 24시간 증가율을 반환한다")
    void returnsCurrentTrendInformation() {
        // given
        Keyword keyword = keyword(50L, "Kubernetes", Domain.DEVELOP);
        Trend trend = trend(32L, keyword);
        KeywordMetric metric = metric(keyword, new BigDecimal("32.4"));
        var pageable = PageRequest.of(0, 20);
        given(keywordRepository.searchByName("kubernetes", Domain.DEVELOP, pageable))
                .willReturn(new PageImpl<>(List.of(keyword), pageable, 1));
        given(trendRepository.findByKeywordIdIn(List.of(50L))).willReturn(List.of(trend));
        given(keywordMetricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                List.of(50L), AnalysisPeriod.HOURS_24,
                TrendFixture.END.minusDays(1), TrendFixture.END)).willReturn(List.of(metric));

        // when
        var response = keywordService.search("  KUBERNETES ", Domain.DEVELOP, 0, 20);

        // then
        var item = response.content().getFirst();
        assertThat(item.keywordId()).isEqualTo(50L);
        assertThat(item.trendId()).isEqualTo(32L);
        assertThat(item.trendTypes()).containsExactly(TrendType.CURRENT);
        assertThat(item.growthRate()).isEqualByComparingTo("32.4");
    }

    @Test
    @DisplayName("현재 트렌드가 아닌 키워드는 트렌드 정보를 비워 반환한다")
    void returnsKeywordWithoutTrendInformation() {
        // given
        Keyword keyword = keyword(51L, "Spring Cloud", Domain.DEVELOP);
        var pageable = PageRequest.of(0, 20);
        given(keywordRepository.searchByName("spring", null, pageable))
                .willReturn(new PageImpl<>(List.of(keyword), pageable, 1));
        given(trendRepository.findByKeywordIdIn(List.of(51L))).willReturn(List.of());

        // when
        var response = keywordService.search("spring", null, 0, 20);

        // then
        var item = response.content().getFirst();
        assertThat(item.trendId()).isNull();
        assertThat(item.trendTypes()).isEmpty();
        assertThat(item.growthRate()).isNull();
    }

    @Test
    @DisplayName("검색 결과가 없으면 추가 조회 없이 빈 content를 반환한다")
    void returnsEmptyContentWithoutAdditionalQueries() {
        // given
        var pageable = PageRequest.of(0, 20);
        given(keywordRepository.searchByName("unknown", null, pageable))
                .willReturn(org.springframework.data.domain.Page.empty(pageable));

        // when
        var response = keywordService.search("unknown", null, 0, 20);

        // then
        assertThat(response.content()).isEmpty();
        then(trendRepository).shouldHaveNoInteractions();
        then(keywordMetricRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("영문 검색어를 소문자로 정규화해 대소문자 구분 없이 검색한다")
    void normalizesEnglishLetterCase() {
        // given
        var pageable = PageRequest.of(0, 20);
        given(keywordRepository.searchByName("ai agent", null, pageable))
                .willReturn(org.springframework.data.domain.Page.empty(pageable));

        // when
        keywordService.search("Ai Agent", null, 0, 20);

        // then
        then(keywordRepository).should().searchByName("ai agent", null, pageable);
    }

    private Keyword keyword(Long id, String name, Domain domain) {
        Keyword keyword = new Keyword(name, domain);
        ReflectionTestUtils.setField(keyword, "id", id);
        return keyword;
    }

    private Trend trend(Long id, Keyword keyword) {
        Trend trend = new Trend(keyword, List.of(TrendType.CURRENT), "설명", null, null,
                TrendFixture.END);
        ReflectionTestUtils.setField(trend, "id", id);
        return trend;
    }

    private KeywordMetric metric(Keyword keyword, BigDecimal growthRate) {
        return KeywordMetric.builder()
                .keyword(keyword)
                .period(AnalysisPeriod.HOURS_24)
                .periodStart(TrendFixture.END.minusDays(1))
                .periodEnd(TrendFixture.END)
                .mentionCount(100)
                .previousMentionCount(75)
                .growthAmount(25)
                .growthRate(growthRate)
                .mentionRank(1)
                .trendTypes(List.of(TrendType.CURRENT))
                .build();
    }
}
