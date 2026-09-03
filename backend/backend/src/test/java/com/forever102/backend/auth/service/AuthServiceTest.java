package com.forever102.backend.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;

import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.member.domain.Member;
import com.forever102.backend.member.repository.MemberRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    private static final String EMAIL = "test@example.com";
    private static final String PASSWORD = "password123!";
    private static final String NICKNAME = "trenduser";
    private static final String ENCODED_PASSWORD = "{bcrypt}$2a$10$encoded";

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @InjectMocks
    private AuthService authService;

    @Test
    @DisplayName("가입에 성공하면 저장된 회원 정보를 응답으로 반환한다")
    void signUpReturnsSavedMember() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(false);
        given(passwordEncoder.encode(PASSWORD)).willReturn(ENCODED_PASSWORD);
        given(memberRepository.saveAndFlush(any(Member.class))).willAnswer(invocation -> {
            Member member = invocation.getArgument(0);
            ReflectionTestUtils.setField(member, "id", 1L);
            return member;
        });

        // when
        SignUpResponse response = authService.signUp(signUpRequest());

        // then
        assertThat(response).isEqualTo(new SignUpResponse(1L, EMAIL, NICKNAME, false));
    }

    @Test
    @DisplayName("비밀번호는 원문이 아닌 해시로 저장된다")
    void signUpStoresHashedPassword() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(false);
        given(passwordEncoder.encode(PASSWORD)).willReturn(ENCODED_PASSWORD);
        given(memberRepository.saveAndFlush(any(Member.class))).willAnswer(invocation -> invocation.getArgument(0));

        // when
        authService.signUp(signUpRequest());

        // then
        ArgumentCaptor<Member> captor = ArgumentCaptor.forClass(Member.class);
        then(memberRepository).should().saveAndFlush(captor.capture());
        assertThat(captor.getValue().getPasswordHash()).isEqualTo(ENCODED_PASSWORD);
    }

    @Test
    @DisplayName("가입 직후 회원의 온보딩은 미완료 상태다")
    void signUpLeavesOnboardingIncomplete() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(false);
        given(passwordEncoder.encode(PASSWORD)).willReturn(ENCODED_PASSWORD);
        given(memberRepository.saveAndFlush(any(Member.class))).willAnswer(invocation -> invocation.getArgument(0));

        // when
        SignUpResponse response = authService.signUp(signUpRequest());

        // then
        assertThat(response.onboardingCompleted()).isFalse();
    }

    @Test
    @DisplayName("이미 가입된 이메일이면 EMAIL_ALREADY_EXISTS 예외가 발생한다")
    void signUpRejectsDuplicatedEmail() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(true);

        // when & then
        assertThatThrownBy(() -> authService.signUp(signUpRequest()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.EMAIL_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("이미 가입된 이메일이면 회원을 저장하지 않는다")
    void signUpDoesNotSaveDuplicatedEmail() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(true);

        // when
        catchThrowable(() -> authService.signUp(signUpRequest()));

        // then
        then(memberRepository).should(never()).saveAndFlush(any(Member.class));
    }

    @Test
    @DisplayName("동시 가입으로 이메일 유니크 제약을 위반하면 EMAIL_ALREADY_EXISTS 예외가 발생한다")
    void signUpTranslatesUniqueViolation() {
        // given
        given(memberRepository.existsByEmail(EMAIL)).willReturn(false);
        given(passwordEncoder.encode(PASSWORD)).willReturn(ENCODED_PASSWORD);
        willThrow(new DataIntegrityViolationException("duplicate key"))
                .given(memberRepository).saveAndFlush(any(Member.class));

        // when & then
        assertThatThrownBy(() -> authService.signUp(signUpRequest()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.EMAIL_ALREADY_EXISTS);
    }

    private SignUpRequest signUpRequest() {
        return new SignUpRequest(EMAIL, PASSWORD, NICKNAME);
    }
}
