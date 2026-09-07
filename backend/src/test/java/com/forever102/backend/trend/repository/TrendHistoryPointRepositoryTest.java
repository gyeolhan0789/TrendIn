package com.forever102.backend.trend.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.domain.HistoryBucketUnit;
import com.forever102.backend.trend.domain.Keyword;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendHistoryPoint;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class TrendHistoryPointRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired TrendHistoryPointRepository repository;

    @Test
    @DisplayName("트렌드와 집계 단위 및 반개방 기간으로 조회해 오름차순으로 반환한다")
    void findsRequestedBucketsInAscendingOrder() {
        Trend trend = persistTrend("Ballet Sneakers");
        Trend other = persistTrend("Java");
        var start = OffsetDateTime.parse("2026-08-30T00:00:00+09:00");
        entityManager.persist(new TrendHistoryPoint(trend, HistoryBucketUnit.HOUR, start.plusHours(2), 0L));
        entityManager.persist(new TrendHistoryPoint(trend, HistoryBucketUnit.HOUR, start, 0L));
        entityManager.persist(new TrendHistoryPoint(trend, HistoryBucketUnit.HOUR, start.plusHours(1), 18L));
        entityManager.persist(new TrendHistoryPoint(trend, HistoryBucketUnit.DAY, start, 99L));
        entityManager.persist(new TrendHistoryPoint(other, HistoryBucketUnit.HOUR, start, 88L));
        entityManager.persist(new TrendHistoryPoint(trend, HistoryBucketUnit.HOUR, start.plusDays(1), 77L));
        entityManager.flush();
        entityManager.clear();

        var points = repository
                .findByTrendIdAndBucketUnitAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        trend.getId(), HistoryBucketUnit.HOUR, start, start.plusDays(1));

        assertThat(points).extracting(TrendHistoryPoint::getBucketStart)
                .containsExactly(start, start.plusHours(1), start.plusHours(2));
        assertThat(points).extracting(TrendHistoryPoint::getMentionCount)
                .containsExactly(0L, 18L, 0L);
    }

    private Trend persistTrend(String keywordName) {
        Keyword keyword = new Keyword(keywordName, Domain.FASHION);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, "설명", OffsetDateTime.parse("2026-08-20T00:00:00+09:00"));
        entityManager.persist(trend);
        return trend;
    }
}
