package com.forever102.notification.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class NotificationReadServiceTest {

    private static final Long MEMBER_ID = 1L;
    private static final Long NOTIFICATION_ID = 30L;

    @Mock NotificationRepository notificationRepository;

    private NotificationReadService service;

    @BeforeEach
    void setUp() {
        service = new NotificationReadService(notificationRepository);
    }

    @Test
    @DisplayName("로그인한 회원의 알림을 읽음 처리한다")
    void marksOwnedNotificationAsRead() {
        // given
        Notification notification = notification(false);
        given(notificationRepository.findByIdAndMemberId(NOTIFICATION_ID, MEMBER_ID))
                .willReturn(Optional.of(notification));

        // when
        service.markAsRead(MEMBER_ID, NOTIFICATION_ID);

        // then
        assertThat(notification.isRead()).isTrue();
    }

    @Test
    @DisplayName("이미 읽은 알림을 다시 요청해도 읽음 상태를 유지한다")
    void keepsAlreadyReadNotificationRead() {
        // given
        Notification notification = notification(true);
        given(notificationRepository.findByIdAndMemberId(NOTIFICATION_ID, MEMBER_ID))
                .willReturn(Optional.of(notification));

        // when
        service.markAsRead(MEMBER_ID, NOTIFICATION_ID);

        // then
        assertThat(notification.isRead()).isTrue();
    }

    @Test
    @DisplayName("존재하지 않거나 다른 회원의 알림은 404 예외로 처리한다")
    void rejectsUnknownOrUnownedNotification() {
        // given
        given(notificationRepository.findByIdAndMemberId(NOTIFICATION_ID, MEMBER_ID))
                .willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> service.markAsRead(MEMBER_ID, NOTIFICATION_ID))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.NOTIFICATION_NOT_FOUND));
    }

    @Test
    @DisplayName("로그인한 회원의 미읽음 알림을 bulk update로 모두 읽음 처리한다")
    void marksAllMemberNotificationsAsRead() {
        // given
        given(notificationRepository.markAllAsReadByMemberId(MEMBER_ID)).willReturn(3);

        // when
        service.markAllAsRead(MEMBER_ID);

        // then
        then(notificationRepository).should().markAllAsReadByMemberId(MEMBER_ID);
    }

    @Test
    @DisplayName("미읽음 알림이 없어도 전체 읽음 요청을 정상 처리한다")
    void acceptsMarkAllWhenNoUnreadNotifications() {
        // given
        given(notificationRepository.markAllAsReadByMemberId(MEMBER_ID)).willReturn(0);

        // when
        service.markAllAsRead(MEMBER_ID);

        // then
        then(notificationRepository).should().markAllAsReadByMemberId(MEMBER_ID);
    }

    private Notification notification(boolean read) {
        Member member = Member.create("member@example.com", "password", "회원");
        Keyword keyword = new Keyword("발레코어", Domain.FASHION);
        Trend trend = new Trend(keyword,
                OffsetDateTime.parse("2026-09-11T00:00:00+09:00"));
        Notification notification = Notification.trendChange(
                member, trend, "트렌드 진입 알림", "TREND_ENTRY:10:2026-09-11T00:00:00Z");
        ReflectionTestUtils.setField(notification, "id", NOTIFICATION_ID);
        ReflectionTestUtils.setField(notification, "read", read);
        return notification;
    }
}
