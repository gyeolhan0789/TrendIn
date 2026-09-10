package com.forever102.member.dto;

import com.forever102.member.domain.SavedTrend;
import java.time.OffsetDateTime;

public record SavedTrendRegisterResponse(
        Long savedTrendId,
        Long trendId,
        OffsetDateTime savedAt
) {
    public static SavedTrendRegisterResponse from(SavedTrend savedTrend) {
        return new SavedTrendRegisterResponse(savedTrend.getId(), savedTrend.getTrend().getId(),
                savedTrend.getCreatedAt());
    }
}
