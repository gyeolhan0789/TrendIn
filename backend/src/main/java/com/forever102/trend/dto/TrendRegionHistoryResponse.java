package com.forever102.trend.dto;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import java.time.OffsetDateTime;
import java.util.List;

public record TrendRegionHistoryResponse(
        Long trendId,
        String countryCode,
        String countryName,
        String period,
        String timezone,
        OffsetDateTime startAt,
        OffsetDateTime endAt,
        List<HistoryPointResponse> history
) {
    public static TrendRegionHistoryResponse of(Long trendId, String countryCode,
            String countryName, AnalysisPeriod period, OffsetDateTime startAt,
            OffsetDateTime endAt, List<HistoryPointResponse> history) {
        return new TrendRegionHistoryResponse(trendId, countryCode, countryName,
                period.getValue(), AnalysisWindow.ANALYSIS_ZONE.getId(), startAt, endAt,
                List.copyOf(history));
    }

    public record HistoryPointResponse(
            OffsetDateTime bucketStart,
            OffsetDateTime bucketEnd,
            long mentionCount
    ) {
    }
}
