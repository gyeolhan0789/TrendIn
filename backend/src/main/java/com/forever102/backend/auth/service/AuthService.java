package com.forever102.backend.auth.service;

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
     */
    @Transactional(readOnly = true)
    public ReissueResponse reissue(ReissueRequest request) {
        Long memberId = jwtTokenProvider.parseRefreshToken(request.refreshToken());
        if (!refreshTokenRepository.matches(memberId, request.refreshToken())) {
            // 서명은 유효하지만 이미 회전됐거나 만료된 토큰이다.
            throw new BusinessException(ErrorCode.INVALID_REFRESH_TOKEN);
        }

        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.INVALID_REFRESH_TOKEN));

        AuthTokens tokens = jwtTokenProvider.issue(memberId);
        refreshTokenRepository.save(memberId, tokens.refreshToken(), tokens.refreshTokenTtl());

        return ReissueResponse.of(tokens, member);
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
