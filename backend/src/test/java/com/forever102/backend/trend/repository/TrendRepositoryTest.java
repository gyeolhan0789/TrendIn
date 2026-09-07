package com.forever102.backend.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.Keyword;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendAiAnalysis;
import com.forever102.backend.trend.domain.TrendAnalysis;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class TrendRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired TrendRepository trendRepository;
    @Autowired TrendAnalysisRepository analysisRepository;
    @Autowired TrendAiAnalysisRepository aiAnalysisRepository;

    @Test
    @DisplayName("요청한 기간에 속한 최신 분석만 조회한다")
    void loadsLatestAnalysisForRequestedPeriod() {
        // given
        Trend trend = persistTrend("Ballet Sneakers");
        persistAnalysis(trend, AnalysisPeriod.HOURS_24, TrendFixture.END.plusDays(1), 24);
        persistAnalysis(trend, AnalysisPeriod.DAYS_7, TrendFixture.END, 7);
        TrendAnalysis latestSevenDays =
                persistAnalysis(trend, AnalysisPeriod.DAYS_7, TrendFixture.END.plusDays(2), 70);
        persistAnalysis(trend, AnalysisPeriod.DAYS_30, TrendFixture.END.plusDays(3), 30);
        entityManager.flush();
        entityManager.clear();
        // when
        TrendAnalysis loaded = analysisRepository
                .findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(trend.getId(), "7D")
                .orElseThrow();
        // then
        assertThat(loaded.getId()).isEqualTo(latestSevenDays.getId());
        assertThat(loaded.getMentionCount()).isEqualTo(70);
        assertThat(loaded.getAnalysisWindow().getRecentStart()).isEqualTo(TrendFixture.END.minusDays(7));
        assertThat(entityManager.createNativeQuery("select period from trend_analyses where id = :id", String.class)
                .setParameter("id", loaded.getId()).getSingleResult()).isEqualTo("7D");
    }

    @Test
    @DisplayName("최신 AI 분석은 기간 지표와 독립적으로 조회하고 출처를 복원한다")
    void loadsLatestAiAnalysisIndependently() {
        // given
        Trend trend = persistTrend("Java");
        TrendAiAnalysis older = new TrendAiAnalysis(trend, "COMPLETED", "이전 요약", "이전 이유",
                java.util.List.of(300L), TrendFixture.END);
        entityManager.persist(older);
        TrendAiAnalysis latest = TrendFixture.aiAnalysis(trend);
        entityManager.persist(latest);
        entityManager.flush();
        entityManager.clear();
        // when
        TrendAiAnalysis loaded = aiAnalysisRepository
                .findFirstByTrendIdOrderByGeneratedAtDescIdDesc(trend.getId()).orElseThrow();
        // then
        assertThat(loaded.getId()).isEqualTo(latest.getId());
        assertThat(loaded.getSourceContentIds()).containsExactly(301L, 302L);
    }

    @Test
    @DisplayName("요청 기간 분석이 없어도 트렌드와 최신 AI 결과를 조합할 수 있다")
    void combinesMissingPeriodAnalysisWithAi() {
        // given
        Trend trend = persistTrend("AI");
        entityManager.persist(TrendFixture.aiAnalysis(trend));
        entityManager.flush();
        entityManager.clear();
        // when
        Trend loadedTrend = trendRepository.findById(trend.getId()).orElseThrow();
        var periodAnalysis = analysisRepository
                .findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(
                        trend.getId(), "30D").orElse(null);
        var ai = aiAnalysisRepository.findFirstByTrendIdOrderByGeneratedAtDescIdDesc(trend.getId()).orElseThrow();
        var response = TrendDetailResponse.from(loadedTrend, periodAnalysis, ai);
        // then
        assertThat(response.mentionCount()).isNull();
        assertThat(response.evidence()).isNull();
        assertThat(response.aiAnalysis().summary()).isNotBlank();
    }

    private Trend persistTrend(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, "짧은 설명", TrendFixture.END.minusDays(4));
        entityManager.persist(trend);
        return trend;
    }

    private TrendAnalysis persistAnalysis(
            Trend trend, AnalysisPeriod period, OffsetDateTime analyzedAt, long count) {
        TrendAnalysis analysis = TrendAnalysis.builder().trend(trend).period(period).trendType("RISING")
                .mentionCount(count).previousMentionCount(0)
                .analysisWindow(TrendFixture.window(period)).analyzedAt(analyzedAt).build();
        entityManager.persist(analysis);
        return analysis;
    }
}
