package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendService {

    private final TrendRepository trendRepository;
    private final KeywordMetricRepository keywordMetricRepository;
    private final Clock trendClock;

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
}
