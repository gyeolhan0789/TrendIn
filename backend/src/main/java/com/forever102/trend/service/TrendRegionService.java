package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordCountryDailyMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.TrendRegionResponse;
import com.forever102.trend.dto.TrendRegionResponse.RegionItemResponse;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendRegionService {

    private static final Set<AnalysisPeriod> SUPPORTED_PERIODS =
            Set.of(AnalysisPeriod.HOURS_24, AnalysisPeriod.DAYS_7);

    private final TrendRepository trendRepository;
    private final KeywordCountryDailyMetricRepository countryMetricRepository;
    private final Clock trendClock;

    public TrendRegionResponse getRegions(Long trendId, AnalysisPeriod period) {
        validatePeriod(period);
        Trend trend = findTrend(trendId);
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        LocalDate startDate = window.getRecentStart().toLocalDate();
        LocalDate endDate = window.getRecentEnd().toLocalDate();

        Map<String, Long> mentionCounts = countryMetricRepository
                .findByKeywordIdAndMetricDateGreaterThanEqualAndMetricDateLessThanOrderByMetricDateAsc(
                        trend.getKeyword().getId(), startDate, endDate).stream()
                .collect(Collectors.groupingBy(KeywordCountryDailyMetric::getCountryCode,
                        Collectors.summingLong(KeywordCountryDailyMetric::getMentionCount)));

        List<Map.Entry<String, Long>> sorted = mentionCounts.entrySet().stream()
                .sorted(Map.Entry.<String, Long>comparingByValue(Comparator.reverseOrder())
                        .thenComparing(Map.Entry.comparingByKey()))
                .toList();
        return TrendRegionResponse.of(trendId, period, startDate, endDate, rank(sorted));
    }

    private Trend findTrend(Long trendId) {
        return trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
    }

    private void validatePeriod(AnalysisPeriod period) {
        if (!SUPPORTED_PERIODS.contains(period)) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
    }

    private List<RegionItemResponse> rank(List<Map.Entry<String, Long>> sorted) {
        List<RegionItemResponse> result = new ArrayList<>();
        long previousCount = Long.MIN_VALUE;
        int rank = 0;
        for (int index = 0; index < sorted.size(); index++) {
            Map.Entry<String, Long> entry = sorted.get(index);
            if (entry.getValue() != previousCount) {
                rank = index + 1;
                previousCount = entry.getValue();
            }
            result.add(new RegionItemResponse(rank, entry.getKey(),
                    countryName(entry.getKey()), entry.getValue()));
        }
        return List.copyOf(result);
    }

    private String countryName(String countryCode) {
        return Locale.of("", countryCode).getDisplayCountry(Locale.KOREAN);
    }
}
