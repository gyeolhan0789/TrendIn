package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.domain.PageRequest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class KeywordSearchRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordRepository keywordRepository;

    private Keyword exact;
    private Keyword partial;
    private Keyword fashion;

    @BeforeEach
    void setUp() {
        partial = persist("Spring Cloud", Domain.DEVELOP);
        exact = persist("Spring", Domain.DEVELOP);
        fashion = persist("Spring Fashion", Domain.FASHION);
        persist("Kubernetes", Domain.DEVELOP);
        persist("AI Agent", Domain.DEVELOP);
        persist("AI Coding", Domain.DEVELOP);
        entityManager.flush();
        entityManager.clear();
    }

    @Test
    @DisplayName("키워드명이 정확히 일치하는 결과를 먼저 반환한다")
    void prioritizesExactMatch() {
        // when
        var result = keywordRepository.searchByName(
                "spring", null, PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).extracting(Keyword::getId)
                .containsExactly(exact.getId(), partial.getId(), fashion.getId());
    }

    @Test
    @DisplayName("선택한 분야의 키워드만 검색한다")
    void filtersByDomain() {
        // when
        var result = keywordRepository.searchByName(
                "spring", Domain.FASHION, PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).extracting(Keyword::getName)
                .containsExactly("Spring Fashion");
    }

    @Test
    @DisplayName("키워드명의 일부만 입력해도 일치하는 키워드를 모두 반환한다")
    void findsPartialMatches() {
        // when
        var result = keywordRepository.searchByName(
                "ai", null, PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).extracting(Keyword::getName)
                .containsExactly("AI Agent", "AI Coding");
    }

    @Test
    @DisplayName("키워드 검색 결과를 요청한 크기로 페이징한다")
    void paginatesSearchResults() {
        // when
        var result = keywordRepository.searchByName(
                "spring", null, PageRequest.of(0, 2));

        // then
        assertThat(result.getContent()).hasSize(2);
        assertThat(result.hasNext()).isTrue();
    }

    @Test
    @DisplayName("일치하는 키워드가 없으면 빈 페이지를 반환한다")
    void returnsEmptyPage() {
        // when
        var result = keywordRepository.searchByName(
                "없는 키워드", null, PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).isEmpty();
    }

    private Keyword persist(String name, Domain domain) {
        Keyword keyword = new Keyword(name, domain);
        entityManager.persist(keyword);
        return keyword;
    }
}
