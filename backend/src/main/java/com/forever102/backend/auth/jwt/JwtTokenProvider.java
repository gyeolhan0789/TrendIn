package com.forever102.backend.auth.jwt;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.JwtParser;
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
    private final JwtParser parser;
    private final Duration accessTokenExpiration;
    private final Duration refreshTokenExpiration;

    public JwtTokenProvider(JwtProperties properties) {
        byte[] secret = properties.secret().getBytes(StandardCharsets.UTF_8);
        if (secret.length < MINIMUM_SECRET_LENGTH) {
            throw new IllegalStateException("jwt.secret은 HS256 서명을 위해 32바이트 이상이어야 합니다.");
        }
        // 시크릿 길이에 따라 서명 알고리즘이 달라지지 않도록 HS256으로 고정한다.
        this.secretKey = new SecretKeySpec(secret, KEY_ALGORITHM);
        this.parser = Jwts.parser().verifyWith(this.secretKey).build();
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

    /**
     * 액세스 토큰을 검증하고 회원 식별자를 꺼낸다.
     * 클라이언트가 재발급으로 분기할 수 있도록 만료는 EXPIRED_TOKEN으로 따로 구분한다.
     */
    public Long parseAccessToken(String token) {
        return parseToken(token, ACCESS_TOKEN_TYPE, ErrorCode.EXPIRED_TOKEN, ErrorCode.INVALID_TOKEN);
    }

    /**
     * 리프레시 토큰을 검증하고 회원 식별자를 꺼낸다.
     * 재발급 실패는 어느 경우든 재로그인으로 이어지므로 만료와 무효를 구분하지 않는다.
     */
    public Long parseRefreshToken(String token) {
        return parseToken(token, REFRESH_TOKEN_TYPE,
                ErrorCode.INVALID_REFRESH_TOKEN, ErrorCode.INVALID_REFRESH_TOKEN);
    }

    private Long parseToken(String token, String expectedType, ErrorCode expiredCode, ErrorCode invalidCode) {
        Claims claims = parseClaims(token, expiredCode, invalidCode);
        if (!expectedType.equals(claims.get(TOKEN_TYPE_CLAIM, String.class))) {
            // 액세스 토큰과 리프레시 토큰을 서로의 자리에 쓰지 못하게 막는다.
            throw new BusinessException(invalidCode);
        }
        return parseMemberId(claims, invalidCode);
    }

    private Claims parseClaims(String token, ErrorCode expiredCode, ErrorCode invalidCode) {
        try {
            return parser.parseSignedClaims(token).getPayload();
        } catch (ExpiredJwtException e) {
            throw new BusinessException(expiredCode);
        } catch (JwtException | IllegalArgumentException e) {
            throw new BusinessException(invalidCode);
        }
    }

    private Long parseMemberId(Claims claims, ErrorCode invalidCode) {
        try {
            return Long.valueOf(claims.getSubject());
        } catch (NumberFormatException e) {
            throw new BusinessException(invalidCode);
        }
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
