package com.forever102.member.repository;

import com.forever102.member.domain.SavedTrend;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SavedTrendRepository extends JpaRepository<SavedTrend, Long> {

    boolean existsByMemberIdAndTrendId(Long memberId, Long trendId);

    Optional<SavedTrend> findByIdAndMemberId(Long id, Long memberId);

    @EntityGraph(attributePaths = {"trend", "trend.keyword"})
    Page<SavedTrend> findAllByMemberIdOrderByCreatedAtDescIdDesc(Long memberId, Pageable pageable);
}
