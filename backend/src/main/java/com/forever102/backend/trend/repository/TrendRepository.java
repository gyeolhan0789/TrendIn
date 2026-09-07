package com.forever102.backend.trend.repository;

import com.forever102.backend.trend.domain.Trend;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendRepository extends JpaRepository<Trend, Long> {

    @Override
    @EntityGraph(attributePaths = "keyword")
    Optional<Trend> findById(Long id);
}
