package com.forever102.backend.trend.service;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.domain.TrendHistoryDataStatus;
import com.forever102.backend.trend.domain.TrendHistoryPoint;
import com.forever102.backend.trend.dto.TrendHistoryResponse;
import com.forever102.backend.trend.dto.TrendHistoryResponse.HistoryPointResponse;
import com.forever102.backend.trend.repository.TrendHistoryPointRepository;
import com.forever102.backend.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.UnaryOperator;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendHistoryService {

    private final TrendRepository trendRepository;
    private final TrendHistoryPointRepository historyPointRepository;
    private final Clock trendClock;

    public TrendHistoryResponse getHistory(Long trendId, AnalysisPeriod period) {
        if (!trendRepository.existsById(trendId)) {
            throw new BusinessException(ErrorCode.TREND_NOT_FOUND);
        }

        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        OffsetDateTime startAt = window.getRecentStart();
        OffsetDateTime endAt = window.getRecentEnd();
        List<TrendHistoryPoint> stored = historyPointRepository
                .findByTrendIdAndBucketUnitAndBucketStartGreaterThanEqualAndBucketStartLessThanOrderByBucketStartAsc(
                        trendId, period.getHistoryBucketUnit(), startAt, endAt);

        if (stored.isEmpty()) {
            return TrendHistoryResponse.of(trendId, period, startAt, endAt,
                    TrendHistoryDataStatus.NO_DATA, List.of());
        }

        Map<Instant, Long> counts = new HashMap<>();
        stored.forEach(point -> counts.put(point.getBucketStart().toInstant(), point.getMentionCount()));
        UnaryOperator<OffsetDateTime> nextBucket = period == AnalysisPeriod.HOURS_24
                ? timestamp -> timestamp.plusHours(1) : timestamp -> timestamp.plusDays(1);
        List<HistoryPointResponse> history = new ArrayList<>();
        for (OffsetDateTime timestamp = startAt; timestamp.isBefore(endAt); timestamp = nextBucket.apply(timestamp)) {
            history.add(new HistoryPointResponse(timestamp, counts.getOrDefault(timestamp.toInstant(), 0L)));
        }
        return TrendHistoryResponse.of(trendId, period, startAt, endAt,
                TrendHistoryDataStatus.AVAILABLE, history);
    }
}
