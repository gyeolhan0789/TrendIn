package com.forever102.backend.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;

import com.forever102.backend.auth.dto.LoginRequest;
import com.forever102.backend.auth.dto.LoginResponse;
import com.forever102.backend.auth.dto.ReissueRequest;
import com.forever102.backend.auth.dto.ReissueResponse;
import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.auth.jwt.AuthTokens;
import com.forever102.backend.auth.jwt.JwtTokenProvider;
import com.forever102.backend.auth.repository.RefreshTokenRepository;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.member.domain.Member;
import com.forever102.backend.member.repository.MemberRepository;
import java.time.Duration;
import java.util.Optional;
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
    private static final Long MEMBER_ID = 1L;
    private static final AuthTokens TOKENS =
            new AuthTokens("access-token", "refresh-token", 900L, 1_209_600L);
    private static final String REFRESH_TOKEN = "refresh-token";
    private static final AuthTokens REISSUED_TOKENS =
            new AuthTokens("new-access-token", "new-refresh-token", 900L, 1_209_600L);

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private JwtTokenProvider jwtTokenProvider;

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

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

    @Test
    @DisplayName("이메일과 비밀번호가 일치하면 액세스·리프레시 토큰을 발급한다")
    void loginIssuesTokens() {
        // given
        givenRegisteredMember();
        given(passwordEncoder.matches(PASSWORD, ENCODED_PASSWORD)).willReturn(true);
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(TOKENS);

        // when
        LoginResponse response = authService.login(loginRequest());

        // then
        assertThat(response).isEqualTo(
                new LoginResponse("access-token", "refresh-token", "Bearer", 900L, 1_209_600L, false)
        );
    }

    @Test
    @DisplayName("로그인에 성공하면 리프레시 토큰을 만료 시간만큼의 TTL로 저장한다")
    void loginStoresRefreshToken() {
        // given
        givenRegisteredMember();
        given(passwordEncoder.matches(PASSWORD, ENCODED_PASSWORD)).willReturn(true);
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(TOKENS);

        // when
        authService.login(loginRequest());

        // then
        then(refreshTokenRepository).should()
                .save(MEMBER_ID, "refresh-token", Duration.ofSeconds(1_209_600L));
    }

    @Test
    @DisplayName("온보딩을 완료한 회원은 응답의 onboardingCompleted가 true다")
    void loginReportsOnboardingCompleted() {
        // given
        Member member = givenRegisteredMember();
        member.completeOnboarding();
        given(passwordEncoder.matches(PASSWORD, ENCODED_PASSWORD)).willReturn(true);
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(TOKENS);

        // when
        LoginResponse response = authService.login(loginRequest());

        // then
        assertThat(response.onboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("비밀번호가 일치하지 않으면 INVALID_CREDENTIALS 예외가 발생한다")
    void loginRejectsWrongPassword() {
        // given
        givenRegisteredMember();
        given(passwordEncoder.matches(PASSWORD, ENCODED_PASSWORD)).willReturn(false);

        // when & then
        assertThatThrownBy(() -> authService.login(loginRequest()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_CREDENTIALS);
    }

    @Test
    @DisplayName("가입되지 않은 이메일도 비밀번호 불일치와 같은 INVALID_CREDENTIALS 예외로 응답한다")
    void loginHidesUnknownEmail() {
        // given
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.login(loginRequest()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_CREDENTIALS);
    }

    @Test
    @DisplayName("비밀번호가 없는 계정은 비밀번호 대조 없이 INVALID_CREDENTIALS 예외가 발생한다")
    void loginRejectsMemberWithoutPassword() {
        // given
        Member member = Member.create(EMAIL, null, NICKNAME);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.of(member));

        // when & then
        assertThatThrownBy(() -> authService.login(loginRequest()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_CREDENTIALS);
    }

    @Test
    @DisplayName("인증에 실패하면 토큰을 발급하거나 저장하지 않는다")
    void loginDoesNotIssueTokensWhenAuthenticationFails() {
        // given
        givenRegisteredMember();
        given(passwordEncoder.matches(PASSWORD, ENCODED_PASSWORD)).willReturn(false);

        // when
        catchThrowable(() -> authService.login(loginRequest()));

        // then
        then(jwtTokenProvider).should(never()).issue(any());
        then(refreshTokenRepository).should(never()).save(any(), any(), any());
    }


    @Test
    @DisplayName("유효한 리프레시 토큰이면 새 토큰 한 쌍을 발급한다")
    void reissueIssuesNewTokens() {
        // given
        givenStoredRefreshToken();
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(REISSUED_TOKENS);

        // when
        ReissueResponse response = authService.reissue(new ReissueRequest(REFRESH_TOKEN));

        // then
        assertThat(response).isEqualTo(new ReissueResponse(
                "new-access-token", "new-refresh-token", "Bearer", 900L, 1_209_600L, false));
    }

    @Test
    @DisplayName("재발급하면 새 리프레시 토큰으로 교체하고 TTL을 다시 설정한다")
    void reissueRotatesStoredRefreshToken() {
        // given
        givenStoredRefreshToken();
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(REISSUED_TOKENS);

        // when
        authService.reissue(new ReissueRequest(REFRESH_TOKEN));

        // then
        then(refreshTokenRepository).should()
                .save(MEMBER_ID, "new-refresh-token", Duration.ofSeconds(1_209_600L));
    }

    @Test
    @DisplayName("온보딩 완료 여부는 저장된 회원 정보에서 읽는다")
    void reissueReportsOnboardingCompleted() {
        // given
        Member member = givenStoredRefreshToken();
        member.completeOnboarding();
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(REISSUED_TOKENS);

        // when
        ReissueResponse response = authService.reissue(new ReissueRequest(REFRESH_TOKEN));

        // then
        assertThat(response.onboardingCompleted()).isTrue();
    }

    @Test
    @DisplayName("저장된 토큰과 다르면 INVALID_REFRESH_TOKEN 예외가 발생한다")
    void reissueRejectsRotatedRefreshToken() {
        // given
        given(jwtTokenProvider.parseRefreshToken(REFRESH_TOKEN)).willReturn(MEMBER_ID);
        given(refreshTokenRepository.matches(MEMBER_ID, REFRESH_TOKEN)).willReturn(false);

        // when & then
        assertThatThrownBy(() -> authService.reissue(new ReissueRequest(REFRESH_TOKEN)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("토큰 검증에 실패하면 회원을 조회하거나 토큰을 발급하지 않는다")
    void reissueDoesNotIssueTokensWhenValidationFails() {
        // given
        given(jwtTokenProvider.parseRefreshToken(REFRESH_TOKEN)).willReturn(MEMBER_ID);
        given(refreshTokenRepository.matches(MEMBER_ID, REFRESH_TOKEN)).willReturn(false);

        // when
        catchThrowable(() -> authService.reissue(new ReissueRequest(REFRESH_TOKEN)));

        // then
        then(memberRepository).should(never()).findById(any());
        then(jwtTokenProvider).should(never()).issue(any());
        then(refreshTokenRepository).should(never()).save(any(), any(), any());
    }

    @Test
    @DisplayName("탈퇴 등으로 회원이 없으면 INVALID_REFRESH_TOKEN 예외가 발생한다")
    void reissueRejectsMissingMember() {
        // given
        given(jwtTokenProvider.parseRefreshToken(REFRESH_TOKEN)).willReturn(MEMBER_ID);
        given(refreshTokenRepository.matches(MEMBER_ID, REFRESH_TOKEN)).willReturn(true);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.reissue(new ReissueRequest(REFRESH_TOKEN)))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.INVALID_REFRESH_TOKEN);
    }

    private Member givenStoredRefreshToken() {
        Member member = Member.create(EMAIL, ENCODED_PASSWORD, NICKNAME);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(jwtTokenProvider.parseRefreshToken(REFRESH_TOKEN)).willReturn(MEMBER_ID);
        given(refreshTokenRepository.matches(MEMBER_ID, REFRESH_TOKEN)).willReturn(true);
        given(memberRepository.findById(MEMBER_ID)).willReturn(Optional.of(member));
        return member;
    }
    private Member givenRegisteredMember() {
        Member member = Member.create(EMAIL, ENCODED_PASSWORD, NICKNAME);
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.of(member));
        return member;
    }

    private LoginRequest loginRequest() {
        return new LoginRequest(EMAIL, PASSWORD);
    }

    private SignUpRequest signUpRequest() {
        return new SignUpRequest(EMAIL, PASSWORD, NICKNAME);
    }
}
