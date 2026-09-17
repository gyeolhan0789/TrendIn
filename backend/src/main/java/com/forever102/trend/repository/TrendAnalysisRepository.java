package com.forever102.trend.repository;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.TrendAnalysis;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendAnalysisRepository extends JpaRepository<TrendAnalysis, Long> {
    Optional<TrendAnalysis> findByTrendIdAndPeriod(Long trendId, AnalysisPeriod period);

    List<TrendAnalysis> findByTrendIdInAndPeriod(Collection<Long> trendIds, AnalysisPeriod period);
}
