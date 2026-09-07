package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.TrendMetric;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendMetricRepository extends JpaRepository<TrendMetric, Long> {

    Optional<TrendMetric> findFirstByTrendIdAndPeriodAndAnalysisWindowRecentStartAndAnalysisWindowRecentEndOrderByAnalyzedAtDescIdDesc(
            Long trendId, String period, OffsetDateTime recentStart, OffsetDateTime recentEnd);
}
