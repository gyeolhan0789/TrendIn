package com.forever102.auth.dto;

import com.forever102.auth.jwt.AuthTokens;
import com.forever102.member.domain.Member;

public record LoginResponse(
        String accessToken,
        String refreshToken,
        String tokenType,
        long accessTokenExpiresIn,
        long refreshTokenExpiresIn,
        boolean onboardingCompleted
) {

    private static final String BEARER = "Bearer";

    public static LoginResponse of(AuthTokens tokens, Member member) {
        return new LoginResponse(
                tokens.accessToken(),
                tokens.refreshToken(),
                BEARER,
                tokens.accessTokenExpiresIn(),
                tokens.refreshTokenExpiresIn(),
                member.isOnboardingCompleted()
        );
    }
}
