package com.forever102.member.service;

import com.forever102.member.domain.SavedTrend;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.repository.SavedTrendRepository;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.repository.KeywordMetricRepository;
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
public class SavedTrendService {

    private final SavedTrendRepository savedTrendRepository;
    private final KeywordMetricRepository keywordMetricRepository;
    private final Clock trendClock;

    public SavedTrendListResponse getSavedTrends(
            Long memberId,
            AnalysisPeriod period,
            int page,
            int size
    ) {
        Page<SavedTrend> savedTrends = savedTrendRepository
                .findAllByMemberIdOrderByCreatedAtDescIdDesc(memberId, PageRequest.of(page, size));
        if (savedTrends.isEmpty()) {
            return SavedTrendListResponse.from(savedTrends, Map.of());
        }

        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        Map<Long, KeywordMetric> metricsByKeywordId = keywordMetricRepository
                .findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                        savedTrends.stream()
                                .map(savedTrend -> savedTrend.getTrend().getKeyword().getId())
                                .toList(),
                        period, window.getRecentStart(), window.getRecentEnd())
                .stream()
                .collect(Collectors.toMap(metric -> metric.getKeyword().getId(), Function.identity()));
        return SavedTrendListResponse.from(savedTrends, metricsByKeywordId);
    }
}
