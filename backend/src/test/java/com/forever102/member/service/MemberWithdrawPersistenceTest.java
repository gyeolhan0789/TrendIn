package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.auth.repository.RefreshTokenRepository;
import com.forever102.member.domain.Domain;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberDomain;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.member.domain.SavedTrend;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.notification.domain.Notification;
import com.forever102.notification.domain.NotificationSetting;
import com.forever102.notification.repository.NotificationRepository;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import jakarta.persistence.EntityManager;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.context.annotation.Import;

/**
 * 탈퇴를 H2와 실제 외래키 제약에서 검증한다.
 *
 * <p><b>단위 시험으로는 이 기능의 핵심을 못 잡는다.</b> 리포지토리를 대역으로 바꾸면 지우는
 * 순서를 확인할 수 있을 뿐, 그 순서가 왜 필요한지 — 외래키가 실제로 막는지 — 는 DB가 있어야
 * 드러난다. {@code member_interest_keywords}와 {@code notifications}에는 ON DELETE CASCADE가
 * 없어, 회원을 먼저 지우면 제약 위반이 난다.
 *
 * <p>Redis는 이 시험의 관심이 아니므로 대역으로 바꾼다. 세션을 끊는지는 단위 시험이 본다.
 */
@DataJpaTest(properties = "spring.jpa.hibernate.ddl-auto=create-drop")
@Import(MemberService.class)
class MemberWithdrawPersistenceTest {

    @Autowired EntityManager entityManager;
    @Autowired MemberRepository memberRepository;
    @Autowired MemberInterestKeywordRepository interestKeywordRepository;
    @Autowired NotificationRepository notificationRepository;
    @Autowired MemberService memberService;

    @MockitoBean RefreshTokenRepository refreshTokenRepository;

    @Test
    @DisplayName("개인 자료를 모두 지우고 회원이 사라진다")
    void removesMemberAndPersonalRows() {
        // given
        Member member = persistMemberWithEverything();
        Long memberId = member.getId();
        flushAndClear();

        // when
        memberService.withdraw(memberId);
        flushAndClear();

        // then
        assertThat(memberRepository.findById(memberId)).isEmpty();
        assertThat(interestKeywordRepository.findAllByMemberIdOrderByIdAsc(memberId)).isEmpty();
        assertThat(notificationRepository.countByMemberIdAndReadFalse(memberId)).isZero();
        assertThat(countOf("MemberDomain", memberId)).isZero();
        assertThat(countOf("SavedTrend", memberId)).isZero();
        assertThat(countOf("NotificationSetting", memberId)).isZero();
    }

    @Test
    @DisplayName("탈퇴해도 여럿이 함께 보는 자료는 남는다")
    void keepsSharedRows() {
        /*
         * 탈퇴한 회원이 담았다는 이유로 트렌드나 키워드를 지우면 남은 회원의 화면이 빈다.
         * 개인 자료만 사라지고 그 자료가 가리키던 공유 자료는 그대로여야 한다.
         */
        // given
        Member member = persistMemberWithEverything();
        Long memberId = member.getId();
        flushAndClear();

        // when
        memberService.withdraw(memberId);
        flushAndClear();

        // then
        assertThat(countAll("Keyword")).isOne();
        assertThat(countAll("Trend")).isOne();
    }

    /** 회원과, 회원을 참조하는 여섯 표의 행을 하나씩 만든다. */
    private Member persistMemberWithEverything() {
        Member member = Member.create("withdraw@example.com", "{bcrypt}$2a$10$hash", "탈퇴할회원");
        entityManager.persist(member);

        Keyword keyword = new Keyword("리액트", Domain.DEVELOP);
        entityManager.persist(keyword);
        Trend trend = new Trend(keyword, OffsetDateTime.parse("2026-09-23T00:00:00+09:00"));
        entityManager.persist(trend);

        entityManager.persist(MemberDomain.register(member, Domain.DEVELOP));
        entityManager.persist(MemberInterestKeyword.register(member, keyword));
        entityManager.persist(SavedTrend.save(member, trend));
        entityManager.persist(NotificationSetting.defaults(member));
        entityManager.persist(Notification.trendChange(member, trend, "알림", "dedup:1"));
        return member;
    }

    private long countOf(String entity, Long memberId) {
        return entityManager
                .createQuery("select count(e) from " + entity + " e where e.member.id = :memberId", Long.class)
                .setParameter("memberId", memberId)
                .getSingleResult();
    }

    private long countAll(String entity) {
        return entityManager
                .createQuery("select count(e) from " + entity + " e", Long.class)
                .getSingleResult();
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
