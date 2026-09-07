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
 * 새로 로그인하거나 재발급하면 기존 토큰을 덮어쓰므로 마지막으로 발급한 토큰만 유효하다.
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

    /**
     * 제시된 리프레시 토큰이 이 회원에게 마지막으로 발급한 토큰인지 확인한다.
     * 이미 회전됐거나 TTL이 지나 사라졌으면 false다.
     */
    public boolean matches(Long memberId, String refreshToken) {
        String stored = redisTemplate.opsForValue().get(key(memberId));
        if (stored == null) {
            return false;
        }
        // 해시 비교 시간으로 토큰을 추측하지 못하도록 상수 시간 비교를 사용한다.
        return MessageDigest.isEqual(
                stored.getBytes(StandardCharsets.UTF_8),
                hash(refreshToken).getBytes(StandardCharsets.UTF_8)
        );
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
