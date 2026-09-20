package com.forever102.notification.dto;

import com.forever102.notification.domain.NotificationSetting;

public record NotificationSettingResponse(
        boolean keywordSurgeEnabled,
        boolean keywordDropEnabled,
        boolean newTrendEnabled,
        boolean trendTurningPointEnabled
) {
    public static NotificationSettingResponse from(NotificationSetting setting) {
        return new NotificationSettingResponse(setting.isKeywordSurgeEnabled(),
                setting.isKeywordDropEnabled(), setting.isNewTrendEnabled(),
                setting.isTrendTurningPointEnabled());
    }
}
