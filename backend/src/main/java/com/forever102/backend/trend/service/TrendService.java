package com.forever102.backend.trend.service;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendMetric;
import com.forever102.backend.trend.domain.TrendAiAnalysis;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import com.forever102.backend.trend.repository.TrendMetricRepository;
import com.forever102.backend.trend.repository.TrendRepository;
import com.forever102.backend.trend.repository.TrendAiAnalysisRepository;
import java.time.Clock;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendService {

    private final TrendRepository trendRepository;
    private final TrendMetricRepository trendMetricRepository;
    private final TrendAiAnalysisRepository trendAiAnalysisRepository;
    private final Clock trendClock;

    public TrendDetailResponse getTrendDetail(Long trendId, AnalysisPeriod period) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        TrendMetric metric = trendMetricRepository
                .findFirstByTrendIdAndPeriodAndAnalysisWindowRecentStartAndAnalysisWindowRecentEndOrderByAnalyzedAtDescIdDesc(
                        trendId, period.getValue(), window.getRecentStart(), window.getRecentEnd()).orElse(null);
        TrendAiAnalysis aiAnalysis = trendAiAnalysisRepository
                .findFirstByTrendIdOrderByGeneratedAtDescIdDesc(trendId).orElse(null);
        return TrendDetailResponse.from(trend, metric, aiAnalysis);
    }
}
