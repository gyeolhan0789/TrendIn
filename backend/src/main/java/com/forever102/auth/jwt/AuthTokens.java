package com.forever102.auth.jwt;

import java.time.Duration;

public record AuthTokens(
        String accessToken,
        String refreshToken,
        long accessTokenExpiresIn,
        long refreshTokenExpiresIn
) {

    public Duration refreshTokenTtl() {
        return Duration.ofSeconds(refreshTokenExpiresIn);
    }
}
