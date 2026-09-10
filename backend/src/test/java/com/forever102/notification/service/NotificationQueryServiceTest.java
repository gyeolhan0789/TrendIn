package com.forever102.notification.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.domain.NotificationType;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class NotificationQueryServiceTest {

    private static final Long MEMBER_ID = 1L;

    @Mock NotificationRepository notificationRepository;

    private NotificationQueryService service;

    @BeforeEach
    void setUp() {
        service = new NotificationQueryService(notificationRepository);
    }

    @Test
    @DisplayName("로그인한 회원의 알림을 최신순 페이지로 조회한다")
    void getsMemberNotifications() {
        // given
        Notification notification = notification();
        PageRequest pageable = PageRequest.of(0, 20);
        given(notificationRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(
                MEMBER_ID, pageable)).willReturn(new PageImpl<>(List.of(notification), pageable, 1));

        // when
        var response = service.getNotifications(MEMBER_ID, 0, 20);

        // then
        assertThat(response.content()).singleElement().satisfies(item -> {
            assertThat(item.notificationId()).isEqualTo(30L);
            assertThat(item.trendId()).isEqualTo(101L);
            assertThat(item.notificationType()).isEqualTo(NotificationType.TREND_CHANGE);
            assertThat(item.message()).isEqualTo("트렌드 진입 알림");
            assertThat(item.isRead()).isFalse();
            assertThat(item.createdAt())
                    .isEqualTo(OffsetDateTime.parse("2026-09-11T00:00:00+09:00"));
        });
        assertThat(response.page()).isZero();
        assertThat(response.size()).isEqualTo(20);
        assertThat(response.hasNext()).isFalse();
    }

    @Test
    @DisplayName("회원의 알림이 없으면 빈 페이지를 반환한다")
    void returnsEmptyNotificationPage() {
        // given
        PageRequest pageable = PageRequest.of(0, 20);
        given(notificationRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(
                MEMBER_ID, pageable)).willReturn(new PageImpl<>(List.of(), pageable, 0));

        // when
        var response = service.getNotifications(MEMBER_ID, 0, 20);

        // then
        assertThat(response.content()).isEmpty();
        assertThat(response.hasNext()).isFalse();
    }

    @Test
    @DisplayName("로그인한 회원의 읽지 않은 알림 개수를 반환한다")
    void getsUnreadNotificationCount() {
        // given
        given(notificationRepository.countByMemberIdAndReadFalse(MEMBER_ID)).willReturn(3L);

        // when
        var response = service.getUnreadCount(MEMBER_ID);

        // then
        assertThat(response.unreadCount()).isEqualTo(3L);
        then(notificationRepository).should().countByMemberIdAndReadFalse(MEMBER_ID);
    }

    @Test
    @DisplayName("읽지 않은 알림이 없으면 0을 반환한다")
    void returnsZeroUnreadNotificationCount() {
        // given
        given(notificationRepository.countByMemberIdAndReadFalse(MEMBER_ID)).willReturn(0L);

        // when
        var response = service.getUnreadCount(MEMBER_ID);

        // then
        assertThat(response.unreadCount()).isZero();
    }

    private Notification notification() {
        Member member = Member.create("member@example.com", "password", "회원");
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        Keyword keyword = new Keyword("발레코어", Domain.FASHION);
        Trend trend = new Trend(keyword, List.of(TrendType.RISING), "설명", null, null,
                OffsetDateTime.parse("2026-09-10T23:50:00+09:00"));
        ReflectionTestUtils.setField(trend, "id", 101L);
        Notification notification = Notification.trendChange(
                member, trend, "트렌드 진입 알림", "TREND_ENTRY:10:2026-09-11T00:00:00+09:00");
        ReflectionTestUtils.setField(notification, "id", 30L);
        ReflectionTestUtils.setField(notification, "createdAt",
                OffsetDateTime.parse("2026-09-11T00:00:00+09:00"));
        return notification;
    }
}
