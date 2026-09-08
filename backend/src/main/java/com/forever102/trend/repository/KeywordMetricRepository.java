package com.forever102.trend.repository;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.KeywordMetric;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KeywordMetricRepository extends JpaRepository<KeywordMetric, Long> {

    Optional<KeywordMetric> findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
            Long keywordId, AnalysisPeriod period, OffsetDateTime periodStart, OffsetDateTime periodEnd);
}
