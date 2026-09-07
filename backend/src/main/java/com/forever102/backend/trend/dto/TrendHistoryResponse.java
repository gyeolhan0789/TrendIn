package com.forever102.backend.trend.dto;

import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.domain.TrendHistoryDataStatus;
import java.time.OffsetDateTime;
import java.util.List;

public record TrendHistoryResponse(
        Long trendId,
        String period,
        String timezone,
        OffsetDateTime startAt,
        OffsetDateTime endAt,
        TrendHistoryDataStatus dataStatus,
        List<HistoryPointResponse> history
) {
    public static TrendHistoryResponse of(Long trendId, AnalysisPeriod period,
            OffsetDateTime startAt, OffsetDateTime endAt,
            TrendHistoryDataStatus dataStatus, List<HistoryPointResponse> history) {
        return new TrendHistoryResponse(trendId, period.getValue(),
                AnalysisWindow.ANALYSIS_ZONE.getId(), startAt, endAt, dataStatus, List.copyOf(history));
    }

    public record HistoryPointResponse(OffsetDateTime timestamp, long mentionCount) {
    }
}
