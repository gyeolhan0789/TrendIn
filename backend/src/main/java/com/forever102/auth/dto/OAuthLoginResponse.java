package com.forever102.auth.dto;

import com.forever102.auth.jwt.AuthTokens;
import com.forever102.member.domain.Member;

public record OAuthLoginResponse(
        String accessToken,
        String refreshToken,
        String tokenType,
        long accessTokenExpiresIn,
        long refreshTokenExpiresIn,
        boolean isNewMember,
        boolean onboardingCompleted
) {

    private static final String BEARER = "Bearer";

    public static OAuthLoginResponse of(AuthTokens tokens, Member member, boolean newMember) {
        return new OAuthLoginResponse(
                tokens.accessToken(),
                tokens.refreshToken(),
                BEARER,
                tokens.accessTokenExpiresIn(),
                tokens.refreshTokenExpiresIn(),
                newMember,
                member.isOnboardingCompleted()
        );
    }
}
