package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.HistoryBucketUnit;
import com.forever102.backend.trend.domain.TrendHistoryPoint;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendHistoryPointRepository extends JpaRepository<TrendHistoryPoint, Long> {

    List<TrendHistoryPoint> findByTrendIdAndBucketUnitAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
            Long trendId, HistoryBucketUnit bucketUnit, OffsetDateTime startAt, OffsetDateTime endAt);
}
