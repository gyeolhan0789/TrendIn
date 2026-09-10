package com.forever102.notification.service;

import com.forever102.notification.dto.NotificationListResponse;
import com.forever102.notification.dto.UnreadNotificationCountResponse;
import com.forever102.notification.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class NotificationQueryService {

    private final NotificationRepository notificationRepository;

    public NotificationListResponse getNotifications(Long memberId, int page, int size) {
        return NotificationListResponse.from(notificationRepository
                .findAllByMemberIdOrderByCreatedAtDescIdDesc(
                        memberId, PageRequest.of(page, size)));
    }

    public UnreadNotificationCountResponse getUnreadCount(Long memberId) {
        return new UnreadNotificationCountResponse(
                notificationRepository.countByMemberIdAndReadFalse(memberId));
    }
}
