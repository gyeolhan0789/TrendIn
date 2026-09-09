package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.dto.TrendContentResponse;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.dto.TrendListResponse;
import com.forever102.trend.repository.ContentRepository;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendService {

    private final TrendRepository trendRepository;
    private final KeywordMetricRepository keywordMetricRepository;
    private final ContentRepository contentRepository;
    private final Clock trendClock;

    public TrendListResponse getTrends(
            Domain domain,
            TrendType type,
            AnalysisPeriod period,
            int page,
            int size
    ) {
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        PageRequest pageable = PageRequest.of(page, size);
        Page<KeywordMetric> metrics = switch (type) {
            case CURRENT -> keywordMetricRepository.findCurrentTrendPage(
                    domain.name(), period.getValue(), window.getRecentStart(), window.getRecentEnd(), pageable);
            case NEW -> keywordMetricRepository.findNewTrendPage(
                    domain.name(), period.getValue(), window.getRecentStart(), window.getRecentEnd(), pageable);
            case RISING -> keywordMetricRepository.findRisingTrendPage(
                    domain.name(), period.getValue(), window.getRecentStart(), window.getRecentEnd(), pageable);
        };
        if (metrics.isEmpty()) {
            return TrendListResponse.from(metrics, Map.of(), window);
        }
        Map<Long, Trend> trendsByKeywordId = trendRepository.findByKeywordIdIn(metrics.stream()
                        .map(metric -> metric.getKeyword().getId()).toList()).stream()
                .collect(Collectors.toMap(trend -> trend.getKeyword().getId(), Function.identity()));
        return TrendListResponse.from(metrics, trendsByKeywordId, window);
    }

    public TrendDetailResponse getTrendDetail(Long trendId, AnalysisPeriod period) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        KeywordMetric metric = keywordMetricRepository
                .findFirstByKeywordIdAndPeriodAndPeriodStartAndPeriodEndOrderByIdDesc(
                        trend.getKeyword().getId(), period,
                        window.getRecentStart(), window.getRecentEnd()).orElse(null);
        return TrendDetailResponse.from(trend, metric, period);
    }

    public TrendContentResponse getTrendContents(Long trendId, int page, int size) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        return TrendContentResponse.from(contentRepository.findByKeywordId(
                trend.getKeyword().getId(), PageRequest.of(page, size)));
    }
}
