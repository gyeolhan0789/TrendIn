package com.forever102.trend.repository;

import com.forever102.trend.domain.KeywordMetricHistory;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KeywordMetricHistoryRepository extends JpaRepository<KeywordMetricHistory, Long> {

    List<KeywordMetricHistory> findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
            Long keywordId, OffsetDateTime startAt, OffsetDateTime endAt);
}
