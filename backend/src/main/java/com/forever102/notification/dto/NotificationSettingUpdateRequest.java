package com.forever102.notification.dto;

import jakarta.validation.constraints.NotNull;

public record NotificationSettingUpdateRequest(
        @NotNull Boolean keywordSurgeEnabled,
        @NotNull Boolean keywordDropEnabled,
        @NotNull Boolean newTrendEnabled,
        @NotNull Boolean trendTurningPointEnabled
) {
}
