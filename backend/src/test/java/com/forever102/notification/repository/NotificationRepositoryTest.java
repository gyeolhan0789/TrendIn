package com.forever102.notification.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.notification.domain.Notification;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
class NotificationRepositoryTest {

    @Autowired EntityManager entityManager;
    @Autowired NotificationRepository notificationRepository;

    @Test
    @DisplayName("관심 키워드에 해당하는 트렌드와 회원을 한 번에 조회한다")
    void findsInterestedTrendTargets() {
        // given
        Member member = persistMember("member@example.com");
        Keyword interestedKeyword = persistKeyword("Ballet Sneakers");
        Keyword unrelatedKeyword = persistKeyword("Unrelated");
        Trend interestedTrend = persistTrend(interestedKeyword);
        persistTrend(unrelatedKeyword);
        entityManager.persist(MemberInterestKeyword.register(member, interestedKeyword));
        entityManager.flush();
        entityManager.clear();

        // when
        List<TrendNotificationTarget> targets = notificationRepository.findTrendNotificationTargets();

        // then
        assertThat(targets).singleElement().satisfies(target -> {
            assertThat(target.interestKeyword().getId()).isNotNull();
            assertThat(target.member().getId()).isEqualTo(member.getId());
            assertThat(target.trend().getId()).isEqualTo(interestedTrend.getId());
            assertThat(target.keyword()).isEqualTo("Ballet Sneakers");
        });
    }

    @Test
    @DisplayName("새 관심 키워드의 직전 트렌드 상태는 false로 저장된다")
    void initializesInterestKeywordAsNotTrending() {
        // given
        Member member = persistMember("member@example.com");
        Keyword keyword = persistKeyword("Ballet Sneakers");
        MemberInterestKeyword interestKeyword = MemberInterestKeyword.register(member, keyword);

        // when
        entityManager.persist(interestKeyword);
        entityManager.flush();
        entityManager.clear();
        MemberInterestKeyword saved = entityManager.find(
                MemberInterestKeyword.class, interestKeyword.getId());

        // then
        assertThat(saved.isWasTrending()).isFalse();
    }

    @Test
    @DisplayName("동일한 dedup key의 알림은 두 번 저장할 수 없다")
    void preventsDuplicateDedupKey() {
        // given
        Member member = persistMember("member@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        notificationRepository.saveAndFlush(notification(member, trend, "TREND_CHANGE:1:1:RISING"));

        // when & then
        assertThatThrownBy(() -> notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_CHANGE:1:1:RISING")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("후보 중 이미 저장된 dedup key만 조회한다")
    void findsExistingDedupKeys() {
        // given
        Member member = persistMember("member@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        String existing = "TREND_CHANGE:1:1:RISING";
        notificationRepository.saveAndFlush(notification(member, trend, existing));

        // when
        List<String> result = notificationRepository.findExistingDedupKeys(
                List.of(existing, "TREND_CHANGE:1:2:NEW"));

        // then
        assertThat(result).containsExactly(existing);
    }

    @Test
    @DisplayName("로그인한 회원의 알림만 최신순으로 조회한다")
    void findsMemberNotificationsInLatestOrder() {
        // given
        Member member = persistMember("member@example.com");
        Member other = persistMember("other@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        Notification first = notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_ENTRY:1:first"));
        Notification second = notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_ENTRY:1:second"));
        notificationRepository.saveAndFlush(notification(other, trend, "TREND_ENTRY:2:first"));
        entityManager.clear();

        // when
        var result = notificationRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(
                member.getId(), PageRequest.of(0, 20));

        // then
        assertThat(result.getContent()).extracting(Notification::getId)
                .containsExactly(second.getId(), first.getId());
        assertThat(result.getContent()).allSatisfy(notification ->
                assertThat(notification.getMember().getId()).isEqualTo(member.getId()));
    }

    @Test
    @DisplayName("회원의 읽지 않은 알림만 집계한다")
    void countsOnlyUnreadMemberNotifications() {
        // given
        Member member = persistMember("member@example.com");
        Member other = persistMember("other@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        Notification read = notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_ENTRY:1:read"));
        ReflectionTestUtils.setField(read, "read", true);
        notificationRepository.saveAndFlush(notification(member, trend, "TREND_ENTRY:1:unread"));
        notificationRepository.saveAndFlush(notification(other, trend, "TREND_ENTRY:2:unread"));
        entityManager.flush();
        entityManager.clear();

        // when
        long count = notificationRepository.countByMemberIdAndReadFalse(member.getId());

        // then
        assertThat(count).isOne();
    }

    @Test
    @DisplayName("알림 식별자와 회원이 모두 일치할 때만 알림을 조회한다")
    void findsNotificationOnlyForOwner() {
        // given
        Member owner = persistMember("owner@example.com");
        Member other = persistMember("other@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        Notification notification = notificationRepository.saveAndFlush(
                notification(owner, trend, "TREND_ENTRY:1:owner"));

        // when
        var owned = notificationRepository.findByIdAndMemberId(
                notification.getId(), owner.getId());
        var unowned = notificationRepository.findByIdAndMemberId(
                notification.getId(), other.getId());

        // then
        assertThat(owned).contains(notification);
        assertThat(unowned).isEmpty();
    }

    @Test
    @DisplayName("회원의 미읽음 알림만 bulk update로 읽음 처리한다")
    void marksOnlyMemberUnreadNotificationsAsRead() {
        // given
        Member member = persistMember("member@example.com");
        Member other = persistMember("other@example.com");
        Trend trend = persistTrend(persistKeyword("Ballet Sneakers"));
        Notification unread = notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_ENTRY:1:unread"));
        Notification alreadyRead = notificationRepository.saveAndFlush(
                notification(member, trend, "TREND_ENTRY:1:read"));
        ReflectionTestUtils.setField(alreadyRead, "read", true);
        Notification otherUnread = notificationRepository.saveAndFlush(
                notification(other, trend, "TREND_ENTRY:2:unread"));
        entityManager.flush();
        entityManager.clear();

        // when
        int updatedCount = notificationRepository.markAllAsReadByMemberId(member.getId());

        // then
        assertThat(updatedCount).isOne();
        assertThat(notificationRepository.findById(unread.getId()).orElseThrow().isRead()).isTrue();
        assertThat(notificationRepository.findById(alreadyRead.getId()).orElseThrow().isRead()).isTrue();
        assertThat(notificationRepository.findById(otherUnread.getId()).orElseThrow().isRead()).isFalse();
    }

    private Notification notification(Member member, Trend trend, String dedupKey) {
        return Notification.trendChange(member, trend, "트렌드 변화 알림", dedupKey);
    }

    private Member persistMember(String email) {
        Member member = Member.create(email, "password-hash", "회원");
        entityManager.persist(member);
        return member;
    }

    private Keyword persistKeyword(String name) {
        Keyword keyword = new Keyword(name, Domain.FASHION);
        entityManager.persist(keyword);
        return keyword;
    }

    private Trend persistTrend(Keyword keyword) {
        Trend trend = new Trend(keyword, List.of(TrendType.RISING), "설명", null, null,
                OffsetDateTime.parse("2026-09-10T00:00:00+09:00"));
        entityManager.persist(trend);
        return trend;
    }
}
