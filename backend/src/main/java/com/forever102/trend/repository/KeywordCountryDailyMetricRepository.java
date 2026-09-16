package com.forever102.trend.repository;

import com.forever102.trend.domain.KeywordCountryDailyMetric;
import java.time.LocalDate;
import java.util.List;
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

    interface CountryFirstDetection {

        String getCountryCode();

        LocalDate getFirstDetectedDate();
    }
}
