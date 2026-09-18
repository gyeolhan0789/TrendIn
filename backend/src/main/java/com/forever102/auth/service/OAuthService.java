package com.forever102.auth.service;

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
import java.util.Locale;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * OAuth 제공자 인증 결과로 가입 또는 로그인을 처리한다.
 *
 * <p>state는 요청 본문으로 받기만 하고 서버가 대조하지 않는다. 인가 URL을 서버가 만들지 않으므로
 * 발급한 state를 서버가 알지 못하기 때문이다. CSRF 방어는 state를 만든 프런트가 콜백에서 비교한다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class OAuthService {

    private static final int NICKNAME_MIN_LENGTH = 2;
    private static final int NICKNAME_MAX_LENGTH = 30;
    private static final String FALLBACK_NICKNAME_PREFIX = "user";

    private final GitLabOAuthClient gitLabOAuthClient;
    private final MemberRepository memberRepository;
    private final MemberOAuthAccountRepository oauthAccountRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenRepository refreshTokenRepository;

    @Transactional
    public OAuthLoginResponse login(String providerName, OAuthLoginRequest request) {
        OAuthProvider provider = OAuthProvider.from(providerName)
                .orElseThrow(() -> new BusinessException(ErrorCode.UNSUPPORTED_PROVIDER));

        OAuthUserInfo userInfo = fetchUserInfo(provider, request.code());
        Resolution resolution = resolveMember(provider, userInfo);

        Member member = resolution.member();
        AuthTokens tokens = jwtTokenProvider.issue(member.getId());
        refreshTokenRepository.save(member.getId(), tokens.refreshToken(), tokens.refreshTokenTtl());

        return OAuthLoginResponse.of(tokens, member, resolution.newMember());
    }

    private OAuthUserInfo fetchUserInfo(OAuthProvider provider, String code) {
        return switch (provider) {
            case GITLAB -> gitLabOAuthClient.fetchUserInfo(code);
        };
    }

    /** 회원을 찾거나 만든 결과. newMember는 이번 요청에서 가입했는지를 뜻한다. */
    private record Resolution(Member member, boolean newMember) {
    }

    /**
     * 연결 → 이메일 → 신규 가입 순으로 회원을 찾는다.
     *
     * <p>이미 이메일·비밀번호로 가입한 회원이 같은 이메일로 로그인하면 계정을 새로 만들지 않고
     * 기존 회원에 연결을 붙인다. 한 사람이 계정 두 개로 쪼개지는 것을 막기 위해서다.
     */
    private Resolution resolveMember(OAuthProvider provider, OAuthUserInfo userInfo) {
        Optional<MemberOAuthAccount> linked =
                oauthAccountRepository.findByProviderAndProviderUserId(provider, userInfo.providerUserId());
        if (linked.isPresent()) {
            return new Resolution(linked.get().getMember(), false);
        }

        // 제공자가 이메일을 주지 않으면 회원을 식별할 수 없다. 권한 범위 설정 문제일 때가 많다.
        if (userInfo.email() == null) {
            log.warn("{} 사용자 정보에 이메일이 없어 로그인을 진행할 수 없다.", provider);
            throw new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED);
        }
        String email = userInfo.email().toLowerCase(Locale.ROOT);

        Optional<Member> existing = memberRepository.findByEmail(email);
        if (existing.isPresent()) {
            link(existing.get(), provider, userInfo.providerUserId());
            return new Resolution(existing.get(), false);
        }

        Member created = memberRepository.save(
                Member.createOAuthMember(email, nickname(userInfo, email)));
        link(created, provider, userInfo.providerUserId());
        return new Resolution(created, true);
    }

    /**
     * 같은 사람이 동시에 두 번 로그인하면 연결이 두 번 만들어질 수 있다.
     * 유니크 제약이 막아 주므로, 위반은 이미 연결됐다는 뜻으로 보고 그 연결을 다시 읽는다.
     */
    private void link(Member member, OAuthProvider provider, String providerUserId) {
        try {
            oauthAccountRepository.saveAndFlush(
                    MemberOAuthAccount.link(member, provider, providerUserId));
        } catch (DataIntegrityViolationException e) {
            log.info("{} 연결이 이미 존재한다. memberId={}", provider, member.getId());
        }
    }

    /**
     * 제공자의 표시명을 회원 닉네임 규칙(2~30자)에 맞춘다.
     * 비어 있거나 너무 짧으면 이메일 앞부분으로 대신한다.
     */
    private String nickname(OAuthUserInfo userInfo, String email) {
        String candidate = trimToLimit(userInfo.nickname());
        if (candidate != null) {
            return candidate;
        }
        String fromEmail = trimToLimit(email.split("@")[0]);
        return fromEmail != null ? fromEmail : FALLBACK_NICKNAME_PREFIX + System.currentTimeMillis() % 100000;
    }

    private String trimToLimit(String value) {
        if (value == null) {
            return null;
        }
        String stripped = value.strip();
        if (stripped.length() < NICKNAME_MIN_LENGTH) {
            return null;
        }
        return stripped.length() > NICKNAME_MAX_LENGTH
                ? stripped.substring(0, NICKNAME_MAX_LENGTH) : stripped;
    }
}
