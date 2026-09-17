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
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class KeywordMetricRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordMetricRepository metricRepository;

    @Test
    @DisplayName("키워드와 요청 기간 및 완료 구간으로 지표를 조회한다")
    void loadsMetricForKeywordAndRequestedPeriod() {
        // given
        Trend trend = persistTrend("Ballet Sneakers");
        KeywordMetric metric = TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123);
        entityManager.persist(metric);
        entityManager.flush();
        entityManager.clear();

        // when
        KeywordMetric loaded = metricRepository
                .findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                        trend.getKeyword().getId(), AnalysisPeriod.DAYS_7,
                        TrendFixture.END.minusDays(7), TrendFixture.END)
                .orElseThrow();

        // then
        assertThat(loaded.getMentionCount()).isEqualTo(430);
        assertThat(loaded.getGrowthAmount()).isEqualTo(307);
        assertThat(loaded.getGrowthRate()).isEqualByComparingTo(new BigDecimal("249.6"));
        assertThat(loaded.getPeriod()).isEqualTo(AnalysisPeriod.DAYS_7);
        assertThat(entityManager.createNativeQuery("select period from keyword_metrics where id = :id", String.class)
                .setParameter("id", loaded.getId()).getSingleResult()).isEqualTo("7D");
    }

    private Trend persistTrend(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword,
                TrendFixture.END);
        entityManager.persist(trend);
        return trend;
    }
}
