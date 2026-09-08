package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetricHistory;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.TrendHistoryResponse;
import com.forever102.trend.dto.TrendHistoryResponse.HistoryPointResponse;
import com.forever102.trend.repository.KeywordMetricHistoryRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendHistoryService {

    private final TrendRepository trendRepository;
    private final KeywordMetricHistoryRepository historyRepository;
    private final Clock trendClock;

    public TrendHistoryResponse getHistory(Long trendId, AnalysisPeriod period) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));

        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        OffsetDateTime startAt = window.getRecentStart();
        OffsetDateTime endAt = window.getRecentEnd();
        List<KeywordMetricHistory> stored = historyRepository
                .findByKeywordIdAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        trend.getKeyword().getId(), startAt, endAt);

        List<HistoryPointResponse> history = new ArrayList<>();
        for (OffsetDateTime bucketStart = startAt; bucketStart.isBefore(endAt);
                bucketStart = bucketStart.plus(period.getHistoryBucketDuration())) {
            OffsetDateTime bucketEnd = bucketStart.plus(period.getHistoryBucketDuration());
            OffsetDateTime currentStart = bucketStart;
            long mentionCount = stored.stream()
                    .filter(point -> !point.getBucketStart().isBefore(currentStart)
                            && point.getBucketStart().isBefore(bucketEnd))
                    .mapToLong(KeywordMetricHistory::getMentionCount)
                    .sum();
            history.add(new HistoryPointResponse(bucketStart, bucketEnd, mentionCount));
        }
        return TrendHistoryResponse.of(trendId, period, startAt, endAt, history);
    }
}
