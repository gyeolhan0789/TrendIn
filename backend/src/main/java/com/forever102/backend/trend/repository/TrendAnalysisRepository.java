package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.TrendAnalysis;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendAnalysisRepository extends JpaRepository<TrendAnalysis, Long> {

    Optional<TrendAnalysis> findFirstByTrendIdAndPeriodOrderByAnalyzedAtDescIdDesc(
            Long trendId, String period);
}
