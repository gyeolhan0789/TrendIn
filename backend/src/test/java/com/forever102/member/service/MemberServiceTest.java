package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.BDDMockito.given;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.repository.MemberRepository;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class MemberServiceTest {

    private static final Long MEMBER_ID = 1L;
    private static final String EMAIL = "test@example.com";
    private static final String NICKNAME = "trenduser";
    private static final String ENCODED_PASSWORD = "{bcrypt}$2a$10$encoded";

    @Mock
    private MemberRepository memberRepository;

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

    private Member givenMember() {
        Member member = Member.create(EMAIL, ENCODED_PASSWORD, NICKNAME);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        return member;
    }
}
