package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import jakarta.persistence.EntityManager;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.domain.PageRequest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class TrendListRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordMetricRepository metricRepository;

    Trend first;
    Trend second;
    Trend risingOnly;

    @BeforeEach
    void setUp() {
        first = persistTrend("첫 번째", Domain.FASHION,
                List.of(TrendType.CURRENT, TrendType.NEW, TrendType.RISING), 1, 100, "10.0");
        second = persistTrend("두 번째", Domain.FASHION,
                List.of(TrendType.CURRENT, TrendType.NEW, TrendType.RISING), 2, 200, "5.0");
        risingOnly = persistTrend("급상승 전용", Domain.FASHION,
                List.of(TrendType.RISING), 3, 300, "20.0");
        persistTrend("다른 분야", Domain.DEVELOP, List.of(TrendType.CURRENT), 4, 400, "30.0");
        entityManager.flush();
        entityManager.clear();
    }

    @Test
    @DisplayName("CURRENT는 유형 포함 여부와 분야를 필터링하고 언급량 순으로 조회한다")
    void findsCurrentTrends() {
        // when
        var result = find(TrendType.CURRENT);

        // then
        assertThat(result.getContent()).extracting(metric -> metric.getKeyword().getId())
                .containsExactly(second.getKeyword().getId(), first.getKeyword().getId());
    }

    @Test
    @DisplayName("NEW는 유형 포함 여부를 필터링하고 언급량 순으로 조회한다")
    void findsNewTrends() {
        // when
        var result = find(TrendType.NEW);

        // then
        assertThat(result.getContent()).extracting(metric -> metric.getKeyword().getId())
                .containsExactly(second.getKeyword().getId(), first.getKeyword().getId());
    }

    @Test
    @DisplayName("RISING은 유형 포함 여부를 필터링하고 증가율 순으로 조회한다")
    void findsRisingTrends() {
        // when
        var result = find(TrendType.RISING);

        // then
        assertThat(result.getContent()).extracting(metric -> metric.getKeyword().getId())
                .containsExactly(risingOnly.getKeyword().getId(),
                        first.getKeyword().getId(), second.getKeyword().getId());
    }

    private org.springframework.data.domain.Page<KeywordMetric> find(TrendType type) {
        var pageable = PageRequest.of(0, 10);
        return switch (type) {
            case CURRENT -> metricRepository.findCurrentTrendPage("FASHION", "7D",
                    TrendFixture.END.minusDays(7), TrendFixture.END, pageable);
            case NEW -> metricRepository.findNewTrendPage("FASHION", "7D",
                    TrendFixture.END.minusDays(7), TrendFixture.END, pageable);
            case RISING -> metricRepository.findRisingTrendPage("FASHION", "7D",
                    TrendFixture.END.minusDays(7), TrendFixture.END, pageable);
        };
    }

    private Trend persistTrend(String keywordName, Domain domain, List<TrendType> types,
            int sequence, long mentionCount, String growthRate) {
        Keyword keyword = new Keyword(keywordName, domain);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, types, keywordName + " 설명", null, null,
                TrendFixture.END.plusHours(sequence));
        entityManager.persist(trend);
        entityManager.persist(KeywordMetric.builder()
                .keyword(keyword)
                .period(AnalysisPeriod.DAYS_7)
                .periodStart(TrendFixture.END.minusDays(7))
                .periodEnd(TrendFixture.END)
                .mentionCount(mentionCount)
                .previousMentionCount(50)
                .growthAmount(mentionCount - 50)
                .growthRate(new BigDecimal(growthRate))
                .mentionRank(sequence)
                .trendTypes(types)
                .build());
        return trend;
    }
}
