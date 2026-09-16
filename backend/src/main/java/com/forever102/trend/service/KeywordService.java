package com.forever102.trend.service;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.KeywordSearchResponse;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class KeywordService {

    private final KeywordRepository keywordRepository;
    private final TrendRepository trendRepository;
    private final KeywordMetricRepository keywordMetricRepository;
    private final Clock trendClock;

    public KeywordSearchResponse search(String query, Domain domain, int page, int size) {
        String normalizedQuery = query.strip().toLowerCase(Locale.ROOT);
        var keywords = keywordRepository.searchByName(
                normalizedQuery, domain, PageRequest.of(page, size));
        if (keywords.isEmpty()) {
            return KeywordSearchResponse.from(keywords, Map.of(), Map.of());
        }

        List<Long> keywordIds = keywords.stream().map(keyword -> keyword.getId()).toList();
        Map<Long, Trend> trendsByKeywordId = trendRepository.findByKeywordIdIn(keywordIds).stream()
                .collect(Collectors.toMap(trend -> trend.getKeyword().getId(), Function.identity()));
        AnalysisWindow window = AnalysisWindow.completed(AnalysisPeriod.HOURS_24, trendClock);
        Map<Long, KeywordMetric> metricsByKeywordId = keywordMetricRepository
                .findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                        keywordIds, AnalysisPeriod.HOURS_24,
                        window.getRecentStart(), window.getRecentEnd()).stream()
                .collect(Collectors.toMap(metric -> metric.getKeyword().getId(), Function.identity()));
        return KeywordSearchResponse.from(keywords, trendsByKeywordId, metricsByKeywordId);
    }
}
