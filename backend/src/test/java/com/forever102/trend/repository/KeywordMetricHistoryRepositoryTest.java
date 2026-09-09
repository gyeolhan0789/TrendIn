package com.forever102.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetricHistory;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class KeywordMetricHistoryRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired KeywordMetricHistoryRepository repository;

    @Test
    @DisplayName("키워드와 반개방 기간으로 시계열을 오름차순 조회한다")
    void findsRequestedBucketsInAscendingOrder() {
        // given
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        Keyword other = new Keyword("Java", Domain.DEVELOP);
        entityManager.persist(keyword);
        entityManager.persist(other);
        var start = OffsetDateTime.parse("2026-08-30T00:00:00+09:00");
        entityManager.persist(new KeywordMetricHistory(keyword, start.plusHours(2), start.plusHours(3), 0L));
        entityManager.persist(new KeywordMetricHistory(keyword, start, start.plusHours(1), 0L));
        entityManager.persist(new KeywordMetricHistory(keyword, start.plusHours(1), start.plusHours(2), 18L));
        entityManager.persist(new KeywordMetricHistory(other, start, start.plusHours(1), 88L));
        entityManager.persist(new KeywordMetricHistory(keyword, start.plusDays(1), start.plusDays(1).plusHours(1), 77L));
        entityManager.flush();
        entityManager.clear();

        // when
        var points = repository
                .findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        keyword.getId(), start, start.plusDays(1));

        // then
        assertThat(points).extracting(KeywordMetricHistory::getBucketStart)
                .containsExactly(start, start.plusHours(1), start.plusHours(2));
        assertThat(points).extracting(KeywordMetricHistory::getMentionCount)
                .containsExactly(0L, 18L, 0L);
    }
}
