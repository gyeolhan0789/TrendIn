package com.forever102.trend.dto;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import java.time.OffsetDateTime;
import java.util.List;

public record TrendHistoryResponse(
        Long trendId,
        String period,
        String timezone,
        OffsetDateTime startAt,
        OffsetDateTime endAt,
        List<HistoryPointResponse> history
) {
    public static TrendHistoryResponse of(Long trendId, AnalysisPeriod period,
            OffsetDateTime startAt, OffsetDateTime endAt, List<HistoryPointResponse> history) {
        return new TrendHistoryResponse(trendId, period.getValue(),
                AnalysisWindow.ANALYSIS_ZONE.getId(), startAt, endAt, List.copyOf(history));
    }

    public record HistoryPointResponse(OffsetDateTime bucketStart, OffsetDateTime bucketEnd,
            long mentionCount) {
    }
}
