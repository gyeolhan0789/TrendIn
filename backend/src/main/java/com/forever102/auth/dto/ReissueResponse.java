package com.forever102.auth.dto;

import com.forever102.auth.jwt.AuthTokens;
import com.forever102.member.domain.Member;

public record ReissueResponse(
        String accessToken,
        String refreshToken,
        String tokenType,
        long accessTokenExpiresIn,
        long refreshTokenExpiresIn,
        boolean onboardingCompleted
) {

    private static final String BEARER = "Bearer";

    public static ReissueResponse of(AuthTokens tokens, Member member) {
        return new ReissueResponse(
                tokens.accessToken(),
                tokens.refreshToken(),
                BEARER,
                tokens.accessTokenExpiresIn(),
                tokens.refreshTokenExpiresIn(),
                member.isOnboardingCompleted()
        );
    }
}
