package com.forever102.backend.auth.jwt;

import io.jsonwebtoken.Jwts;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;

@Component
public class JwtTokenProvider {

    public static final String TOKEN_TYPE_CLAIM = "typ";
    public static final String ACCESS_TOKEN_TYPE = "access";
    public static final String REFRESH_TOKEN_TYPE = "refresh";

    private static final int MINIMUM_SECRET_LENGTH = 32;
    private static final String KEY_ALGORITHM = "HmacSHA256";

    private final SecretKey secretKey;
    private final Duration accessTokenExpiration;
    private final Duration refreshTokenExpiration;

    public JwtTokenProvider(JwtProperties properties) {
        byte[] secret = properties.secret().getBytes(StandardCharsets.UTF_8);
        if (secret.length < MINIMUM_SECRET_LENGTH) {
            throw new IllegalStateException("jwt.secret은 HS256 서명을 위해 32바이트 이상이어야 합니다.");
        }
        // 시크릿 길이에 따라 서명 알고리즘이 달라지지 않도록 HS256으로 고정한다.
        this.secretKey = new SecretKeySpec(secret, KEY_ALGORITHM);
        this.accessTokenExpiration = properties.accessTokenExpiration();
        this.refreshTokenExpiration = properties.refreshTokenExpiration();
    }

    public AuthTokens issue(Long memberId) {
        Instant issuedAt = Instant.now();
        return new AuthTokens(
                createToken(memberId, ACCESS_TOKEN_TYPE, issuedAt, accessTokenExpiration),
                createToken(memberId, REFRESH_TOKEN_TYPE, issuedAt, refreshTokenExpiration),
                accessTokenExpiration.toSeconds(),
                refreshTokenExpiration.toSeconds()
        );
    }

    private String createToken(Long memberId, String tokenType, Instant issuedAt, Duration expiration) {
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(String.valueOf(memberId))
                .claim(TOKEN_TYPE_CLAIM, tokenType)
                .issuedAt(Date.from(issuedAt))
                .expiration(Date.from(issuedAt.plus(expiration)))
                .signWith(secretKey, Jwts.SIG.HS256)
                .compact();
    }
}
