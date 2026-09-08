package com.forever102.trend.repository;

import com.forever102.trend.domain.Trend;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TrendRepository extends JpaRepository<Trend, Long> {

    @Override
    @EntityGraph(attributePaths = "keyword")
    Optional<Trend> findById(Long id);

    @EntityGraph(attributePaths = "keyword")
    List<Trend> findByKeywordIdIn(Collection<Long> keywordIds);
}
