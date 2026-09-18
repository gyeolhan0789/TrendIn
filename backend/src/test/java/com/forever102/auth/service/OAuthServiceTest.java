package com.forever102.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;

import com.forever102.auth.domain.OAuthProvider;
import com.forever102.auth.dto.OAuthLoginRequest;
import com.forever102.auth.dto.OAuthLoginResponse;
import com.forever102.auth.jwt.AuthTokens;
import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.auth.oauth.GitLabOAuthClient;
import com.forever102.auth.oauth.OAuthUserInfo;
import com.forever102.auth.repository.RefreshTokenRepository;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberOAuthAccount;
import com.forever102.member.repository.MemberOAuthAccountRepository;
import com.forever102.member.repository.MemberRepository;
import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class OAuthServiceTest {

    private static final Long MEMBER_ID = 1L;
    private static final String PROVIDER_USER_ID = "4821";
    private static final String EMAIL = "trend@example.com";
    private static final String CODE = "example-authorization-code";
    private static final String STATE = "example-state";
    private static final AuthTokens TOKENS =
            new AuthTokens("access-token", "refresh-token", 900L, 1_209_600L);

    @Mock
    private GitLabOAuthClient gitLabOAuthClient;

    @Mock
    private MemberRepository memberRepository;

    @Mock
    private MemberOAuthAccountRepository oauthAccountRepository;

    @Mock
    private JwtTokenProvider jwtTokenProvider;

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @InjectMocks
    private OAuthService oauthService;

    @Test
    @DisplayName("이미 연결된 계정이면 같은 회원으로 로그인하고 신규 가입이 아니다")
    void logsInLinkedMember() {
        // given
        Member member = member(EMAIL);
        givenLinked(member);
        givenTokens();

        // when
        OAuthLoginResponse response = oauthService.login("gitlab", request());

        // then
        assertThat(response.isNewMember()).isFalse();
        assertThat(response.accessToken()).isEqualTo("access-token");
    }

    @Test
    @DisplayName("이미 연결된 계정이면 회원을 새로 만들지 않는다")
    void doesNotCreateMemberWhenAlreadyLinked() {
        // given
        givenLinked(member(EMAIL));
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        then(memberRepository).should(never()).save(any(Member.class));
        then(oauthAccountRepository).should(never()).saveAndFlush(any(MemberOAuthAccount.class));
    }

    @Test
    @DisplayName("연결은 없지만 같은 이메일의 회원이 있으면 기존 계정에 연결한다")
    void linksToExistingMemberWithSameEmail() {
        // given
        Member member = member(EMAIL);
        givenNotLinked();
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.of(member));
        givenTokens();

        // when
        OAuthLoginResponse response = oauthService.login("gitlab", request());

        // then
        assertThat(response.isNewMember()).isFalse();
        then(memberRepository).should(never()).save(any(Member.class));
        ArgumentCaptor<MemberOAuthAccount> captor = ArgumentCaptor.captor();
        then(oauthAccountRepository).should().saveAndFlush(captor.capture());
        assertThat(captor.getValue().getMember()).isSameAs(member);
        assertThat(captor.getValue().getProvider()).isEqualTo(OAuthProvider.GITLAB);
    }

    @Test
    @DisplayName("연결도 회원도 없으면 새로 가입시키고 신규 가입으로 표시한다")
    void createsNewMember() {
        // given
        givenNotLinked();
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());
        givenSaveAssignsId();
        givenTokens();

        // when
        OAuthLoginResponse response = oauthService.login("gitlab", request());

        // then
        assertThat(response.isNewMember()).isTrue();
        assertThat(response.onboardingCompleted()).isFalse();
    }

    @Test
    @DisplayName("새로 가입한 회원은 비밀번호가 없다")
    void createdMemberHasNoPassword() {
        // given
        givenNotLinked();
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());
        givenSaveAssignsId();
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        ArgumentCaptor<Member> captor = ArgumentCaptor.captor();
        then(memberRepository).should().save(captor.capture());
        assertThat(captor.getValue().getPasswordHash()).isNull();
        assertThat(captor.getValue().getEmail()).isEqualTo(EMAIL);
    }

    @Test
    @DisplayName("제공자 이메일은 소문자로 맞춰 저장한다")
    void normalizesEmailToLowerCase() {
        // given
        givenNotLinkedWith(new OAuthUserInfo(PROVIDER_USER_ID, "Trend@Example.COM", "트렌드"));
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());
        givenSaveAssignsId();
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        then(memberRepository).should().findByEmail(EMAIL);
    }

    @Test
    @DisplayName("제공자 표시명이 30자를 넘으면 잘라서 닉네임으로 쓴다")
    void trimsLongNickname() {
        // given
        givenNotLinkedWith(new OAuthUserInfo(PROVIDER_USER_ID, EMAIL, "가".repeat(40)));
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());
        givenSaveAssignsId();
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        ArgumentCaptor<Member> captor = ArgumentCaptor.captor();
        then(memberRepository).should().save(captor.capture());
        assertThat(captor.getValue().getNickname()).hasSize(30);
    }

    @Test
    @DisplayName("제공자 표시명이 없으면 이메일 앞부분을 닉네임으로 쓴다")
    void fallsBackToEmailLocalPart() {
        // given
        givenNotLinkedWith(new OAuthUserInfo(PROVIDER_USER_ID, EMAIL, null));
        given(memberRepository.findByEmail(EMAIL)).willReturn(Optional.empty());
        givenSaveAssignsId();
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        ArgumentCaptor<Member> captor = ArgumentCaptor.captor();
        then(memberRepository).should().save(captor.capture());
        assertThat(captor.getValue().getNickname()).isEqualTo("trend");
    }

    @Test
    @DisplayName("로그인에 성공하면 리프레시 토큰을 만료 시간만큼의 TTL로 저장한다")
    void storesRefreshToken() {
        // given
        givenLinked(member(EMAIL));
        givenTokens();

        // when
        oauthService.login("gitlab", request());

        // then
        then(refreshTokenRepository).should()
                .save(MEMBER_ID, "refresh-token", Duration.ofSeconds(1_209_600L));
    }

    @Test
    @DisplayName("제공자 이름은 대소문자를 가리지 않는다")
    void acceptsProviderNameCaseInsensitively() {
        // given
        givenLinked(member(EMAIL));
        givenTokens();

        // when & then
        assertThat(oauthService.login("GitLab", request())).isNotNull();
    }

    @Test
    @DisplayName("지원하지 않는 제공자면 UNSUPPORTED_PROVIDER 예외가 발생한다")
    void rejectsUnsupportedProvider() {
        // when & then
        assertThatThrownBy(() -> oauthService.login("github", request()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.UNSUPPORTED_PROVIDER);
    }

    @Test
    @DisplayName("지원하지 않는 제공자면 제공자에 요청하지 않는다")
    void doesNotCallProviderWhenUnsupported() {
        // when
        catchThrowable(() -> oauthService.login("github", request()));

        // then
        then(gitLabOAuthClient).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("제공자 인증 실패는 그대로 전달한다")
    void propagatesAuthenticationFailure() {
        // given
        willThrow(new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED))
                .given(gitLabOAuthClient).fetchUserInfo(CODE);

        // when & then
        assertThatThrownBy(() -> oauthService.login("gitlab", request()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.OAUTH_AUTHENTICATION_FAILED);
    }

    @Test
    @DisplayName("제공자가 이메일을 주지 않으면 OAUTH_AUTHENTICATION_FAILED 예외가 발생한다")
    void rejectsMissingEmail() {
        // given
        givenNotLinkedWith(new OAuthUserInfo(PROVIDER_USER_ID, null, "트렌드"));

        // when & then
        assertThatThrownBy(() -> oauthService.login("gitlab", request()))
                .isInstanceOf(BusinessException.class)
                .hasFieldOrPropertyWithValue("errorCode", ErrorCode.OAUTH_AUTHENTICATION_FAILED);
    }

    @Test
    @DisplayName("인증에 실패하면 토큰을 발급하거나 저장하지 않는다")
    void doesNotIssueTokensWhenAuthenticationFails() {
        // given
        willThrow(new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED))
                .given(gitLabOAuthClient).fetchUserInfo(CODE);

        // when
        catchThrowable(() -> oauthService.login("gitlab", request()));

        // then
        then(jwtTokenProvider).should(never()).issue(any());
        then(refreshTokenRepository).should(never()).save(any(), any(), any());
    }

    private OAuthLoginRequest request() {
        return new OAuthLoginRequest(CODE, STATE);
    }

    private Member member(String email) {
        Member member = Member.createOAuthMember(email, "트렌드");
        ReflectionTestUtils.setField(member, "id", MEMBER_ID);
        return member;
    }

    private void givenLinked(Member member) {
        given(gitLabOAuthClient.fetchUserInfo(CODE))
                .willReturn(new OAuthUserInfo(PROVIDER_USER_ID, EMAIL, "트렌드"));
        given(oauthAccountRepository.findByProviderAndProviderUserId(OAuthProvider.GITLAB, PROVIDER_USER_ID))
                .willReturn(Optional.of(MemberOAuthAccount.link(member, OAuthProvider.GITLAB, PROVIDER_USER_ID)));
    }

    private void givenNotLinked() {
        givenNotLinkedWith(new OAuthUserInfo(PROVIDER_USER_ID, EMAIL, "트렌드"));
    }

    private void givenNotLinkedWith(OAuthUserInfo userInfo) {
        given(gitLabOAuthClient.fetchUserInfo(CODE)).willReturn(userInfo);
        given(oauthAccountRepository.findByProviderAndProviderUserId(OAuthProvider.GITLAB, PROVIDER_USER_ID))
                .willReturn(Optional.empty());
    }

    private void givenSaveAssignsId() {
        given(memberRepository.save(any(Member.class))).willAnswer(invocation -> {
            Member saved = invocation.getArgument(0);
            ReflectionTestUtils.setField(saved, "id", MEMBER_ID);
            return saved;
        });
    }

    private void givenTokens() {
        given(jwtTokenProvider.issue(MEMBER_ID)).willReturn(TOKENS);
    }
}
