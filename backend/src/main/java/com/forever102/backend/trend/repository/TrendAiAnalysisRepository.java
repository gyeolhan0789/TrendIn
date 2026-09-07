package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.TrendAiAnalysis;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendAiAnalysisRepository extends JpaRepository<TrendAiAnalysis, Long> {

    Optional<TrendAiAnalysis> findFirstByTrendIdOrderByGeneratedAtDescIdDesc(Long trendId);
}
