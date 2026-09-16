package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordCountryDailyMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.TrendRegionHistoryResponse;
import com.forever102.trend.dto.TrendRegionHistoryResponse.HistoryPointResponse;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendRegionHistoryService {

    private static final Pattern COUNTRY_CODE = Pattern.compile("[A-Z]{2}");
    private static final Set<AnalysisPeriod> SUPPORTED_PERIODS =
            Set.of(AnalysisPeriod.HOURS_24, AnalysisPeriod.DAYS_7);

    private final TrendRepository trendRepository;
    private final KeywordCountryDailyMetricRepository countryMetricRepository;
    private final Clock trendClock;

    public TrendRegionHistoryResponse getHistory(
            Long trendId, String countryCode, AnalysisPeriod period) {
        validatePeriod(period);
        String normalizedCountryCode = normalizeCountryCode(countryCode);
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        OffsetDateTime startAt = window.getRecentStart();
        OffsetDateTime endAt = window.getRecentEnd();

        List<KeywordCountryDailyMetric> stored = countryMetricRepository
                .findByKeywordIdAndCountryCodeAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        trend.getKeyword().getId(), normalizedCountryCode,
                        startAt.toLocalDate(), endAt.toLocalDate());
        Map<LocalDate, KeywordCountryDailyMetric> byDate = stored.stream()
                .collect(Collectors.toMap(KeywordCountryDailyMetric::getMetricDate,
                        Function.identity()));

        List<HistoryPointResponse> history = new ArrayList<>();
        for (OffsetDateTime bucketStart = startAt; bucketStart.isBefore(endAt);
                bucketStart = bucketStart.plusDays(1)) {
            KeywordCountryDailyMetric metric = byDate.get(bucketStart.toLocalDate());
            history.add(new HistoryPointResponse(bucketStart, bucketStart.plusDays(1),
                    metric == null ? 0L : metric.getMentionCount()));
        }
        return TrendRegionHistoryResponse.of(trendId, normalizedCountryCode,
                countryName(normalizedCountryCode), period, startAt, endAt, history);
    }

    private void validatePeriod(AnalysisPeriod period) {
        if (!SUPPORTED_PERIODS.contains(period)) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
    }

    private String normalizeCountryCode(String countryCode) {
        String normalized = countryCode == null ? "" : countryCode.strip().toUpperCase(Locale.ROOT);
        if (!COUNTRY_CODE.matcher(normalized).matches()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        return normalized;
    }

    private String countryName(String countryCode) {
        return Locale.of("", countryCode).getDisplayCountry(Locale.KOREAN);
    }
}
