package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Content;
import com.forever102.trend.domain.Keyword;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.data.domain.PageRequest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class ContentRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired ContentRepository contentRepository;

    @Test
    @DisplayName("키워드에 연결된 콘텐츠만 게시일 최신순으로 조회한다")
    void findsRelatedContentsByKeyword() {
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        Keyword otherKeyword = new Keyword("AI Agent", Domain.DEVELOP);
        entityManager.persist(keyword);
        entityManager.persist(otherKeyword);
        Content older = content("older", "2026-08-29T10:00:00+09:00");
        Content newer = content("newer", "2026-08-30T10:00:00+09:00");
        Content unrelated = content("unrelated", "2026-08-31T10:00:00+09:00");
        older.addKeyword(keyword);
        newer.addKeyword(keyword);
        unrelated.addKeyword(otherKeyword);
        contentRepository.save(older);
        contentRepository.save(newer);
        contentRepository.save(unrelated);
        entityManager.flush();
        entityManager.clear();

        var result = contentRepository.findByKeywordId(keyword.getId(), PageRequest.of(0, 10));

        assertThat(result.getContent()).extracting(Content::getTitle)
                .containsExactly("newer", "older");
        assertThat(result.getTotalElements()).isEqualTo(2);
    }

    private Content content(String title, String publishedAt) {
        OffsetDateTime published = OffsetDateTime.parse(publishedAt);
        return new Content(title, "source", "https://example.com/" + title,
                "curated/" + title + ".parquet", published, published.plusHours(1));
    }
}
