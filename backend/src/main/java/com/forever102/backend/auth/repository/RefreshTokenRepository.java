package com.forever102.backend.auth.repository;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

/**
 * 회원당 하나의 리프레시 토큰을 Redis에 보관한다.
 * 새로 로그인하면 기존 토큰을 덮어쓰므로 마지막 로그인만 유효하다.
 * Redis 덤프가 유출되어도 토큰을 그대로 쓸 수 없도록 원문이 아닌 SHA-256 해시를 저장한다.
 */
@Repository
@RequiredArgsConstructor
public class RefreshTokenRepository {

    private static final String KEY_PREFIX = "refresh:member:";
    private static final String HASH_ALGORITHM = "SHA-256";

    private final StringRedisTemplate redisTemplate;

    public void save(Long memberId, String refreshToken, Duration ttl) {
        redisTemplate.opsForValue().set(key(memberId), hash(refreshToken), ttl);
    }

    private String key(Long memberId) {
        return KEY_PREFIX + memberId;
    }

    private String hash(String refreshToken) {
        try {
            MessageDigest digest = MessageDigest.getInstance(HASH_ALGORITHM);
            return HexFormat.of().formatHex(digest.digest(refreshToken.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 알고리즘을 사용할 수 없습니다.", e);
        }
    }
}
