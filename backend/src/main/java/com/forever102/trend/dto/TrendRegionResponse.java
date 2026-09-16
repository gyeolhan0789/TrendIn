package com.forever102.trend.dto;

import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import java.time.LocalDate;
import java.util.List;

public record TrendRegionResponse(
        Long trendId,
        String period,
        String timezone,
        LocalDate startDate,
        LocalDate endDate,
        List<RegionItemResponse> regions
) {
    public static TrendRegionResponse of(Long trendId, AnalysisPeriod period,
            LocalDate startDate, LocalDate endDate, List<RegionItemResponse> regions) {
        return new TrendRegionResponse(trendId, period.getValue(),
                AnalysisWindow.ANALYSIS_ZONE.getId(), startDate, endDate, List.copyOf(regions));
    }

    public record RegionItemResponse(
            int rank,
            String countryCode,
            String countryName,
            long mentionCount
    ) {
    }
}
