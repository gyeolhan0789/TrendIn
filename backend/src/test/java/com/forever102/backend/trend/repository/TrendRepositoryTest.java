package com.forever102.backend.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.Keyword;
import com.forever102.backend.trend.domain.Trend;
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

    @Autowired
    private EntityManager entityManager;
    @Autowired
    private TrendRepository trendRepository;
    @Autowired
    private TrendAnalysisRepository analysisRepository;

    @Test
    @DisplayName("해당 트렌드의 최신 분석을 선택하고 JSON 근거와 AI 출처를 복원한다")
    void loadsLatestAnalysisAndPersistedMetadata() {
        // given
        Trend trend = persistTrend("Ballet Sneakers");
        Trend other = persistTrend("Other");
        persistAnalysis(trend, TrendFixture.END, 1);
        TrendAnalysis latest = TrendFixture.analysis(trend, 430, 123);
        entityManager.persist(latest);
        persistAnalysis(other, TrendFixture.END.plusDays(5), 999);
        Long expectedId = latest.getId();
        entityManager.flush();
        entityManager.clear();
        // when
        Trend loadedTrend = trendRepository.findById(trend.getId()).orElseThrow();
        TrendAnalysis loaded = analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(trend.getId()).orElseThrow();
        TrendDetailResponse response = TrendDetailResponse.from(loadedTrend, loaded);
        // then
        assertThat(loaded.getId()).isEqualTo(expectedId);
        assertThat(entityManager.getEntityManagerFactory().getPersistenceUnitUtil().isLoaded(loadedTrend, "keyword")).isTrue();
        assertThat(response.mentionCount()).isEqualTo(430);
        assertThat(response.evidence().appliedThresholds().get("minimumMentionCount")).isEqualByComparingTo("100");
        assertThat(response.aiAnalysis().sourceContentIds()).containsExactly(301L, 302L);
        assertThat(response.analysisWindow().recentEnd().toInstant()).isEqualTo(TrendFixture.END.toInstant());
    }

    @Test
    @DisplayName("분석 시각이 같으면 더 큰 ID로 최신 결과를 결정한다")
    void breaksTimestampTiesById() {
        // given
        Trend trend = persistTrend("Java");
        persistAnalysis(trend, TrendFixture.END, 1);
        TrendAnalysis second = persistAnalysis(trend, TrendFixture.END, 2);
        entityManager.flush();
        entityManager.clear();
        // when & then
        assertThat(analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(trend.getId()).orElseThrow().getId())
                .isEqualTo(second.getId());
    }

    @Test
    @DisplayName("분석이나 AI 결과가 없는 상태를 데이터베이스 조회 후에도 구분한다")
    void preservesMissingAnalysisAndAi() {
        // given
        Trend trend = persistTrend("Java");
        assertThat(analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(trend.getId())).isEmpty();
        persistAnalysis(trend, TrendFixture.END, 0);
        entityManager.flush();
        entityManager.clear();
        // when
        var analysis = analysisRepository.findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(trend.getId()).orElseThrow();
        var response = TrendDetailResponse.from(trendRepository.findById(trend.getId()).orElseThrow(), analysis);
        // then
        assertThat(response.mentionCount()).isZero();
        assertThat(response.growthRate()).isNull();
        assertThat(response.evidence()).isNull();
        assertThat(response.aiAnalysis()).isNull();
    }

    private Trend persistTrend(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, "짧은 설명", TrendFixture.END.minusDays(4));
        entityManager.persist(trend);
        return trend;
    }

    private TrendAnalysis persistAnalysis(Trend trend, OffsetDateTime analyzedAt, long count) {
        TrendAnalysis analysis = TrendAnalysis.builder().trend(trend).trendType("RISING")
                .mentionCount(count).previousMentionCount(0).analysisWindow(TrendFixture.window())
                .analyzedAt(analyzedAt).build();
        entityManager.persist(analysis);
        return analysis;
    }
}
