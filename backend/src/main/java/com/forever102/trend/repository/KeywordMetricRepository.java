package com.forever102.trend.repository;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.KeywordMetric;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface KeywordMetricRepository extends JpaRepository<KeywordMetric, Long> {

    Optional<KeywordMetric> findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
            Long keywordId, AnalysisPeriod period, OffsetDateTime periodStart, OffsetDateTime periodEnd);

    @Query(value = """
            select metric.*
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('CURRENT' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            order by metric.mention_count desc, trend.id asc
            """,
            countQuery = """
            select count(*)
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('CURRENT' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            """, nativeQuery = true)
    Page<KeywordMetric> findCurrentTrendPage(
            @Param("domain") String domain,
            @Param("period") String period,
            @Param("startAt") OffsetDateTime startAt,
            @Param("endAt") OffsetDateTime endAt,
            Pageable pageable);

    @Query(value = """
            select metric.*
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('NEW' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            order by trend.updated_at desc, trend.id asc
            """,
            countQuery = """
            select count(*)
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('NEW' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            """, nativeQuery = true)
    Page<KeywordMetric> findNewTrendPage(
            @Param("domain") String domain,
            @Param("period") String period,
            @Param("startAt") OffsetDateTime startAt,
            @Param("endAt") OffsetDateTime endAt,
            Pageable pageable);

    @Query(value = """
            select metric.*
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('RISING' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            order by metric.growth_rate desc nulls last, trend.id asc
            """,
            countQuery = """
            select count(*)
            from keyword_metrics metric
            join keywords keyword on keyword.id = metric.keyword_id
            join trends trend on trend.keyword_id = keyword.id
            where keyword.domain = :domain
              and cast('RISING' as trend_type) = any(trend.trend_types)
              and metric.period = cast(:period as metric_period)
              and metric.period_start = :startAt
              and metric.period_end = :endAt
            """, nativeQuery = true)
    Page<KeywordMetric> findRisingTrendPage(
            @Param("domain") String domain,
            @Param("period") String period,
            @Param("startAt") OffsetDateTime startAt,
            @Param("endAt") OffsetDateTime endAt,
            Pageable pageable);
}
