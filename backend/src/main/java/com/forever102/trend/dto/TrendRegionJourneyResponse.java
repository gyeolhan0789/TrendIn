package com.forever102.trend.dto;

import com.forever102.trend.domain.AnalysisWindow;
import java.time.LocalDate;
import java.util.List;

public record TrendRegionJourneyResponse(
        Long trendId,
        String period,
        String timezone,
        LocalDate startDate,
        LocalDate endDate,
        List<JourneyItemResponse> regions
) {
    public static TrendRegionJourneyResponse of(Long trendId, LocalDate startDate,
            LocalDate endDate, List<JourneyItemResponse> regions) {
        return new TrendRegionJourneyResponse(trendId, "30D",
                AnalysisWindow.ANALYSIS_ZONE.getId(), startDate, endDate, List.copyOf(regions));
    }

    public record JourneyItemResponse(
            String countryCode,
            String countryName,
            LocalDate firstDetectedDate,
            int order
    ) {
    }
}
