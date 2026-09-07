package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.TrendAnalysis;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendAnalysisRepository extends JpaRepository<TrendAnalysis, Long> {

    Optional<TrendAnalysis> findFirstByTrendIdAndPeriodAndAnalysisWindowRecentStartAndAnalysisWindowRecentEndOrderByAnalyzedAtDescIdDesc(
            Long trendId, String period, OffsetDateTime recentStart, OffsetDateTime recentEnd);
}
