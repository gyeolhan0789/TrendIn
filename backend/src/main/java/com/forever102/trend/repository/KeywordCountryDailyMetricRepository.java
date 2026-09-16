package com.forever102.trend.repository;

import com.forever102.trend.domain.KeywordCountryDailyMetric;
import java.time.LocalDate;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface KeywordCountryDailyMetricRepository
        extends JpaRepository<KeywordCountryDailyMetric, Long> {

    List<KeywordCountryDailyMetric>
            findByKeywordIdAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                    Long keywordId, LocalDate startDate, LocalDate endDate);

    List<KeywordCountryDailyMetric>
            findByKeywordIdAndCountryCodeAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                    Long keywordId, String countryCode, LocalDate startDate, LocalDate endDate);
}
