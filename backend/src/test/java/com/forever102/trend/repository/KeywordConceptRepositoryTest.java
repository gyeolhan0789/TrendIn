package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import jakarta.persistence.EntityManager;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;

@DataJpaTest
@Import(KeywordConceptRepository.class)
class KeywordConceptRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordConceptRepository keywordConceptRepository;

    @Test
    @DisplayName("정규화 이름이 표현과 같은 키워드에 그 개념의 대표 이름을 붙인다")
    void findsConceptNameByNormalizedName() {
        // given
        Keyword leather = persistKeyword("Pelle");
        Keyword unknown = persistKeyword("낯선 말");
        insertConcept(1L, "leather", "ACTIVE");
        insertExpression(11L, 1L, "it", "pelle", "ACTIVE");

        // when
        var names = keywordConceptRepository.findConceptNames(List.of(leather.getId(), unknown.getId()));

        // then
        assertThat(names).containsExactlyEntriesOf(Map.of(leather.getId(), "leather"));
    }

    @Test
    @DisplayName("한 표기가 두 개념에 걸리면 어느 쪽 이름도 붙이지 않는다")
    void skipsAmbiguousExpression() {
        // given
        Keyword dior = persistKeyword("크리스찬 디올");
        insertConcept(2L, "Christian Dior", "ACTIVE");
        insertConcept(3L, "Dior", "ACTIVE");
        insertExpression(21L, 2L, "ko", "크리스찬 디올", "ACTIVE");
        insertExpression(22L, 3L, "ko", "크리스찬 디올", "ACTIVE");

        // when & then
        assertThat(keywordConceptRepository.findConceptNames(List.of(dior.getId()))).isEmpty();
    }

    @Test
    @DisplayName("거절된 표현과 활성이 아닌 개념은 잇지 않는다")
    void ignoresInactiveRows() {
        // given
        Keyword rejected = persistKeyword("룩");
        Keyword merged = persistKeyword("청바지");
        insertConcept(4L, "look", "ACTIVE");
        insertConcept(5L, "jeans", "MERGED");
        insertExpression(41L, 4L, "ko", "룩", "REJECTED");
        insertExpression(51L, 5L, "ko", "청바지", "ACTIVE");

        // when & then
        assertThat(keywordConceptRepository.findConceptNames(
                List.of(rejected.getId(), merged.getId()))).isEmpty();
    }

    @Test
    @DisplayName("원문이 영어 표현이면 이름을 붙이지 않는다. 여러 언어에 걸려도 하나가 영어면 같다")
    void skipsEnglishExpression() {
        // given
        Keyword accessories = persistKeyword("accessories");
        Keyword toryBurch = persistKeyword("Tory Burch");
        insertConcept(6L, "accessory", "ACTIVE");
        insertConcept(7L, "Tory Burch LLC", "ACTIVE");
        insertExpression(61L, 6L, "en", "accessories", "ACTIVE");
        insertExpression(71L, 7L, "en", "tory burch", "ACTIVE");
        insertExpression(72L, 7L, "fr", "tory burch", "ACTIVE");

        // when & then
        assertThat(keywordConceptRepository.findConceptNames(
                List.of(accessories.getId(), toryBurch.getId()))).isEmpty();
    }

    private Keyword persistKeyword(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        entityManager.flush();
        return keyword;
    }

    private void insertConcept(long id, String canonicalName, String status) {
        entityManager.createNativeQuery(
                        "insert into pl_concept (id, canonical_name, status) values (?1, ?2, ?3)")
                .setParameter(1, id)
                .setParameter(2, canonicalName)
                .setParameter(3, status)
                .executeUpdate();
    }

    private void insertExpression(long id, long conceptId, String lang, String normalized, String status) {
        entityManager.createNativeQuery(
                        "insert into pl_concept_expression (id, concept_id, lang, normalized, status) "
                                + "values (?1, ?2, ?3, ?4, ?5)")
                .setParameter(1, id)
                .setParameter(2, conceptId)
                .setParameter(3, lang)
                .setParameter(4, normalized)
                .setParameter(5, status)
                .executeUpdate();
    }
}
