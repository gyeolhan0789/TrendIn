package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordRelation;
import jakarta.persistence.EntityManager;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class KeywordRelationRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordRelationRepository keywordRelationRepository;

    @Test
    @DisplayName("source 키워드의 관계만 점수 내림차순으로 조회한다")
    void findsRelationsBySourceKeyword() {
        // given
        Keyword source = persistKeyword("Ballet Sneakers");
        Keyword first = persistKeyword("Mary Jane Sneakers");
        Keyword second = persistKeyword("Retro Sneakers");
        Keyword unrelatedSource = persistKeyword("Minimal Look");
        persistRelation(source, second, "65.00");
        persistRelation(source, first, "90.00");
        persistRelation(source, source, "100.00");
        persistRelation(unrelatedSource, first, "99.00");
        entityManager.flush();
        entityManager.clear();

        // when
        var result = keywordRelationRepository
                .findBySourceKeywordIdOrderByScore(source.getId());

        // then
        assertThat(result).extracting(relation -> relation.getTargetKeyword().getName())
                .containsExactly("Mary Jane Sneakers", "Retro Sneakers");
        assertThat(result).extracting(KeywordRelation::getRelationScore)
                .satisfiesExactly(
                        score -> assertThat(score).isEqualByComparingTo("90.00"),
                        score -> assertThat(score).isEqualByComparingTo("65.00"));
    }

    @Test
    @DisplayName("관계 점수가 같으면 target 키워드 ID 오름차순으로 조회한다")
    void stabilizesEqualScoreOrder() {
        // given
        Keyword source = persistKeyword("Ballet Sneakers");
        Keyword first = persistKeyword("First");
        Keyword second = persistKeyword("Second");
        persistRelation(source, second, "70.00");
        persistRelation(source, first, "70.00");
        entityManager.flush();
        entityManager.clear();

        // when
        var result = keywordRelationRepository
                .findBySourceKeywordIdOrderByScore(source.getId());

        // then
        assertThat(result).extracting(relation -> relation.getTargetKeyword().getId())
                .containsExactly(first.getId(), second.getId());
    }

    @Test
    @DisplayName("관계 점수는 소수 둘째 자리로 저장한다")
    void storesRelationScoreToTwoDecimalPlaces() {
        // given
        Keyword source = persistKeyword("Ballet Sneakers");
        Keyword target = persistKeyword("Mary Jane Sneakers");
        persistRelation(source, target, "87.555");
        entityManager.flush();
        entityManager.clear();

        // when
        var result = keywordRelationRepository
                .findBySourceKeywordIdOrderByScore(source.getId());

        // then
        assertThat(result).singleElement().extracting(KeywordRelation::getRelationScore)
                .isEqualTo(new BigDecimal("87.56"));
    }

    private Keyword persistKeyword(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        return keyword;
    }

    private void persistRelation(Keyword source, Keyword target, String score) {
        entityManager.persist(new KeywordRelation(source, target, new BigDecimal(score), 10,
                OffsetDateTime.parse("2026-08-31T08:00:00+09:00")));
    }
}
