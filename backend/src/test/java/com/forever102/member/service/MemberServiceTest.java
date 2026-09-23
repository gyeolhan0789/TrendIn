package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.inOrder;

import com.forever102.auth.repository.RefreshTokenRepository;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.member.repository.MemberInterestKeywordRepository;
import com.forever102.member.repository.MemberRepository;
import com.forever102.notification.repository.NotificationRepository;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class MemberServiceTest {

    private static final Long MEMBER_ID = 1L;
    private static final String EMAIL = "test@example.com";
    private static final String NICKNAME = "trenduser";
    private static final String NEW_NICKNAME = "newNickname";
    private static final String ENCODED_PASSWORD = "{bcrypt}$2a$10$encoded";

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private MemberInterestKeywordRepository interestKeywordRepository;

    @Mock
    private NotificationRepository notificationRepository;

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @InjectMocks
    private MemberService memberService;

    @Test
    @DisplayName("회원 식별자로 본인의 회원 정보를 조회한다")
    void returnsMyInfo() {
        // given
        givenMember();

        // when
        MemberInfoResponse response = memberService.getMyInfo(MEMBER_ID);

        // then
        assertThat(response).isEqualTo(new MemberInfoResponse(MEMBER_ID, EMAIL, NICKNAME, false));
    }

    @Test
    @DisplayName("온보딩을 완료한 회원은 onboardingCompleted가 true다")
    void reportsOnboardingCompleted() {
        // given
        givenMember().completeOnboarding();

        // when
        MemberInfoResponse response = memberService.getMyInfo(MEMBER_ID);

        // then
        assertThat(response.onboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("비밀번호 해시는 응답에 포함하지 않는다")
    void doesNotExposePassword() {
        // given
        givenMember();

        // when
        MemberInfoResponse response = memberService.getMyInfo(MEMBER_ID);

        // then
        assertThat(response.toString()).doesNotContain(ENCODED_PASSWORD);
    }

    @Test
    @DisplayName("토큰의 회원이 남아 있지 않으면 MEMBER_NOT_FOUND 예외가 발생한다")
    void rejectsMissingMember() {
        // given
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> memberService.getMyInfo(MEMBER_ID))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.MEMBER_NOT_FOUND);
    }


    @Test
    @DisplayName("닉네임을 수정하면 바뀐 회원 정보를 반환한다")
    void updatesNickname() {
        // given
        givenMember();

        // when
        MemberInfoResponse response = memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NEW_NICKNAME));

        // then
        assertThat(response).isEqualTo(new MemberInfoResponse(MEMBER_ID, EMAIL, NEW_NICKNAME, false));
    }

    @Test
    @DisplayName("수정은 저장된 회원 엔티티에 반영된다")
    void appliesNicknameToMember() {
        // given
        Member member = givenMember();

        // when
        memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NEW_NICKNAME));

        // then
        assertThat(member.getNickname()).isEqualTo(NEW_NICKNAME);
    }

    @Test
    @DisplayName("닉네임 외의 정보는 수정하지 않는다")
    void doesNotChangeOtherFields() {
        // given
        Member member = givenMember();

        // when
        memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NEW_NICKNAME));

        // then
        assertThat(member.getEmail()).isEqualTo(EMAIL);
        assertThat(member.getPasswordHash()).isEqualTo(ENCODED_PASSWORD);
        assertThat(member.isOnboardingCompleted()).isFalse();
    }

    @Test
    @DisplayName("온보딩을 완료한 회원은 수정 후에도 onboardingCompleted가 true다")
    void keepsOnboardingCompletedAfterUpdate() {
        // given
        givenMember().completeOnboarding();

        // when
        MemberInfoResponse response = memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NEW_NICKNAME));

        // then
        assertThat(response.onboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("같은 닉네임을 쓰는 회원이 있어도 수정을 막지 않는다")
    void allowsDuplicatedNickname() {
        // given
        givenMember();

        // when
        MemberInfoResponse response = memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NICKNAME));

        // then
        assertThat(response.nickname()).isEqualTo(NICKNAME);
    }

    @Test
    @DisplayName("토큰의 회원이 남아 있지 않으면 MEMBER_NOT_FOUND 예외가 발생한다")
    void rejectsUpdateForMissingMember() {
        // given
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> memberService.updateMyInfo(MEMBER_ID, new MemberUpdateRequest(NEW_NICKNAME)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.MEMBER_NOT_FOUND);
    }
    @Test
    @DisplayName("탈퇴는 CASCADE가 없는 표를 먼저 비우고 회원을 지운다")
    void withdrawsDeletingChildrenFirst() {
        /*
         * 순서가 곧 계약이다. member_interest_keywords 와 notifications 의 외래키에는
         * ON DELETE CASCADE가 없어, 회원을 먼저 지우면 DB가 외래키 위반으로 막는다.
         */
        // given
        Member member = givenMember();

        // when
        memberService.withdraw(MEMBER_ID);

        // then
        InOrder order = inOrder(interestKeywordRepository, notificationRepository, memberRepository);
        order.verify(interestKeywordRepository).deleteAllByMemberId(MEMBER_ID);
        order.verify(notificationRepository).deleteAllByMemberId(MEMBER_ID);
        order.verify(memberRepository).delete(member);
    }

    @Test
    @DisplayName("탈퇴하면 토큰을 확인하지 않고 세션을 끊는다")
    void withdrawRevokesSession() {
        /*
         * 로그아웃과 다르다. 로그아웃은 제시된 토큰이 현재 세션일 때만 지우지만, 탈퇴는
         * 들고 있는 토큰이 무엇이든 끊어야 한다. 회원이 사라진 뒤 남은 키는 되살릴 수도 없다.
         */
        // given
        givenMember();

        // when
        memberService.withdraw(MEMBER_ID);

        // then
        then(refreshTokenRepository).should().deleteAll(MEMBER_ID);
    }

    @Test
    @DisplayName("토큰의 회원이 남아 있지 않으면 탈퇴가 MEMBER_NOT_FOUND 예외를 낸다")
    void rejectsWithdrawForMissingMember() {
        // given
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> memberService.withdraw(MEMBER_ID))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.MEMBER_NOT_FOUND);
        /* 회원을 찾지 못했으면 아무것도 지우지 않는다 — 세션도 남긴다. */
        then(interestKeywordRepository).shouldHaveNoInteractions();
        then(notificationRepository).shouldHaveNoInteractions();
        then(refreshTokenRepository).shouldHaveNoInteractions();
    }

    private Member givenMember() {
        Member member = Member.create(EMAIL, ENCODED_PASSWORD, NICKNAME);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        return member;
    }
}
