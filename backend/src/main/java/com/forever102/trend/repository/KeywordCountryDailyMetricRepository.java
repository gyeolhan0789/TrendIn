package com.forever102.trend.repository;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.KeywordCountryDailyMetric;
import java.time.LocalDate;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface KeywordCountryDailyMetricRepository
        extends JpaRepository<KeywordCountryDailyMetric, Long> {

    List<KeywordCountryDailyMetric>
            findByKeywordIdAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                    Long keywordId, LocalDate startDate, LocalDate endDate);

    List<KeywordCountryDailyMetric>
            findByKeywordIdAndCountryCodeAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                    Long keywordId, String countryCode, LocalDate startDate, LocalDate endDate);

    @Query("""
            select metric.countryCode as countryCode, min(metric.metricDate) as firstDetectedDate
            from KeywordCountryDailyMetric metric
            where metric.keyword.id = :keywordId
              and metric.metricDate >= :startDate
              and metric.metricDate < :endDate
              and metric.mentionCount > 0
            group by metric.countryCode
            order by min(metric.metricDate), metric.countryCode
            """)
    List<CountryFirstDetection> findCountryFirstDetections(
            @Param("keywordId") Long keywordId,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate);

    /**
     * 한 분야에서 나라마다 몇 번 언급됐는지 키워드를 가리지 않고 합칩니다. 지도를 칠하는 값입니다.
     * 언급이 0인 나라는 지도에서 칠할 것이 없으므로 아예 빼고 셉니다.
     */
    @Query("""
            select metric.countryCode as countryCode, sum(metric.mentionCount) as mentionCount
            from KeywordCountryDailyMetric metric
            where metric.keyword.domain = :domain
              and metric.metricDate >= :startDate
              and metric.metricDate < :endDate
            group by metric.countryCode
            having sum(metric.mentionCount) > 0
            order by sum(metric.mentionCount) desc, metric.countryCode
            """)
    List<CountryMentionTotal> findCountryTotals(
            @Param("domain") Domain domain,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate);

    /** 나라 하나에서 많이 언급된 키워드 순서입니다. 나라를 고르면 보는 TOP 트렌드가 여기서 나옵니다. */
    @Query("""
            select metric.keyword.id as keywordId, sum(metric.mentionCount) as mentionCount
            from KeywordCountryDailyMetric metric
            where metric.keyword.domain = :domain
              and metric.countryCode = :countryCode
              and metric.metricDate >= :startDate
              and metric.metricDate < :endDate
            group by metric.keyword.id
            having sum(metric.mentionCount) > 0
            order by sum(metric.mentionCount) desc, metric.keyword.id
            """)
    List<KeywordMentionTotal> findKeywordTotalsInCountry(
            @Param("domain") Domain domain,
            @Param("countryCode") String countryCode,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate,
            Pageable pageable);

    /** 나라 하나의 전체 언급량. 위 목록을 잘라 내도 몫을 제대로 내려면 자르기 전 합이 필요합니다. */
    @Query("""
            select coalesce(sum(metric.mentionCount), 0)
            from KeywordCountryDailyMetric metric
            where metric.keyword.domain = :domain
              and metric.countryCode = :countryCode
              and metric.metricDate >= :startDate
              and metric.metricDate < :endDate
            """)
    long sumMentionsInCountry(
            @Param("domain") Domain domain,
            @Param("countryCode") String countryCode,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate);

    interface CountryFirstDetection {

        String getCountryCode();

        LocalDate getFirstDetectedDate();
    }

    interface CountryMentionTotal {

        String getCountryCode();

        long getMentionCount();
    }

    interface KeywordMentionTotal {

        Long getKeywordId();

        long getMentionCount();
    }
}
