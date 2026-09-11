package com.forever102.auth.service;

import com.forever102.auth.dto.EmailCheckRequest;
import com.forever102.auth.dto.EmailCheckResponse;
import com.forever102.auth.dto.LoginRequest;
import com.forever102.auth.dto.LoginResponse;
import com.forever102.auth.dto.LogoutRequest;
import com.forever102.auth.dto.ReissueRequest;
import com.forever102.auth.dto.ReissueResponse;
import com.forever102.auth.dto.SignUpRequest;
import com.forever102.auth.dto.SignUpResponse;
import com.forever102.auth.jwt.AuthTokens;
import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.auth.repository.RefreshTokenRepository;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.repository.MemberRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class AuthService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final RefreshTokenRepository refreshTokenRepository;

    public SignUpResponse signUp(SignUpRequest request) {
        if (memberRepository.existsByEmail(request.email())) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }

        Member member = Member.create(
                request.email(),
                passwordEncoder.encode(request.password()),
                request.nickname()
        );

        return SignUpResponse.from(save(member));
    }

    /**
     * 회원가입 전에 해당 이메일로 가입할 수 있는지 확인한다.
     * 확인 이후에도 가입 상태가 바뀔 수 있으므로 회원가입에서 다시 중복을 검사한다.
     */
    @Transactional(readOnly = true)
    public EmailCheckResponse checkEmail(EmailCheckRequest request) {
        return EmailCheckResponse.of(!memberRepository.existsByEmail(request.email()));
    }

    @Transactional(readOnly = true)
    public LoginResponse login(LoginRequest request) {
        Member member = memberRepository.findByEmail(request.email())
                .filter(found -> matches(request.password(), found.getPasswordHash()))
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_CREDENTIALS));

        AuthTokens tokens = jwtTokenProvider.issue(member.getId());
        refreshTokenRepository.save(member.getId(), tokens.refreshToken(), tokens.refreshTokenTtl());

        return LoginResponse.of(tokens, member);
    }

    /**
     * 유효한 리프레시 토큰을 새 토큰 한 쌍으로 교환한다.
     * 리프레시 토큰도 함께 회전시켜 방금 사용한 토큰은 즉시 무효가 된다.
     * 검증과 교체를 원자적으로 처리하므로, 같은 토큰으로 동시에 들어온 재발급·로그아웃 중 하나만 성공한다.
     */
    @Transactional(readOnly = true)
    public ReissueResponse reissue(ReissueRequest request) {
        Long memberId = jwtTokenProvider.parseRefreshToken(request.refreshToken());
        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_REFRESH_TOKEN));

        // 교체할 새 토큰이 있어야 한 번의 왕복으로 검증까지 끝낼 수 있어 발급을 먼저 한다.
        AuthTokens tokens = jwtTokenProvider.issue(memberId);
        if (!refreshTokenRepository.rotate(
                memberId, request.refreshToken(), tokens.refreshToken(), tokens.refreshTokenTtl())) {
            // 서명은 유효하지만 이미 회전됐거나 로그아웃으로 사라진 토큰이다. 발급한 토큰은 저장하지 않고 버린다.
            throw new BusinessException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        return ReissueResponse.of(tokens, member);
    }

    /**
     * 현재 세션을 종료한다. 저장된 리프레시 토큰을 지워 이후 재발급을 막는다.
     * 액세스 토큰은 상태를 두지 않으므로 남은 유효 기간(최대 15분) 동안은 그대로 동작한다.
     */
    @Transactional(readOnly = true)
    public void logout(Long memberId, LogoutRequest request) {
        Long tokenMemberId = jwtTokenProvider.parseRefreshToken(request.refreshToken(), ErrorCode.INVALID_TOKEN);
        if (!tokenMemberId.equals(memberId)
                || !refreshTokenRepository.deleteIfMatches(memberId, request.refreshToken())) {
            // 다른 회원의 토큰이거나, 이미 회전·삭제되어 현재 세션과 일치하지 않는 토큰이다.
            throw new BusinessException(ErrorCode.INVALID_TOKEN);
        }
    }

    private boolean matches(String rawPassword, String passwordHash) {
        return passwordHash != null && passwordEncoder.matches(rawPassword, passwordHash);
    }

    private Member save(Member member) {
        try {
            return memberRepository.saveAndFlush(member);
        } catch (DataIntegrityViolationException e) {
            throw new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }
    }
}
