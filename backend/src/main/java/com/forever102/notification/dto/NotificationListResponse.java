package com.forever102.notification.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.domain.NotificationType;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.data.domain.Page;

public record NotificationListResponse(
        List<NotificationResponse> content,
        int page,
        int size,
        boolean hasNext
) {
    public static NotificationListResponse from(Page<Notification> notifications) {
        return new NotificationListResponse(
                notifications.getContent().stream().map(NotificationResponse::from).toList(),
                notifications.getNumber(), notifications.getSize(), notifications.hasNext());
    }

    public record NotificationResponse(
            Long notificationId,
            Long trendId,
            NotificationType notificationType,
            String message,
            @JsonProperty("isRead") boolean isRead,
            OffsetDateTime createdAt
    ) {
        private static NotificationResponse from(Notification notification) {
            return new NotificationResponse(notification.getId(), notification.getTrend().getId(),
                    notification.getNotificationType(), notification.getMessage(),
                    notification.isRead(), notification.getCreatedAt());
        }
    }
}
