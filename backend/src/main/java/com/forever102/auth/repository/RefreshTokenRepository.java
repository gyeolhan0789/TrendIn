package com.forever102.auth.repository;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Repository;

/**
 * 회원당 하나의 리프레시 토큰을 Redis에 보관한다.
 * 새로 로그인하거나 재발급하면 기존 토큰을 덮어쓰므로 마지막으로 발급한 토큰만 유효하다.
 * Redis 덤프가 유출되어도 토큰을 그대로 쓸 수 없도록 원문이 아닌 SHA-256 해시를 저장한다.
 *
 * <p>재발급과 로그아웃은 검증과 쓰기를 한 번의 왕복으로 처리한다.
 * 읽고 나서 쓰는 사이에 다른 요청이 끼어들면 로그아웃이 지운 키를 재발급이 되살릴 수 있기 때문이다.
 * Redis는 스크립트를 직렬로 실행하므로 아래 두 스크립트가 각각 원자 단위가 되고,
 * 같은 토큰으로 동시에 들어온 요청은 하나만 성공한다.
 */
@Repository
@RequiredArgsConstructor
public class RefreshTokenRepository {

    private static final String KEY_PREFIX = "refresh:member:";
    private static final String HASH_ALGORITHM = "SHA-256";
    private static final Long SUCCESS = 1L;

    /** 저장된 해시가 제시된 토큰의 것과 같을 때만 새 토큰으로 교체한다. */
    private static final RedisScript<Long> ROTATE = RedisScript.of("""
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
                return 1
            end
            return 0
            """, Long.class);

    /** 저장된 해시가 제시된 토큰의 것과 같을 때만 삭제한다. */
    private static final RedisScript<Long> DELETE_IF_MATCHES = RedisScript.of("""
            if redis.call('GET', KEYS[1]) == ARGV[1] then
                return redis.call('DEL', KEYS[1])
            end
            return 0
            """, Long.class);

    private final StringRedisTemplate redisTemplate;

    /**
     * 로그인으로 새 세션을 시작한다. 기존 세션이 있으면 무조건 덮어쓴다.
     */
    public void save(Long memberId, String refreshToken, Duration ttl) {
        redisTemplate.opsForValue().set(key(memberId), hash(refreshToken), ttl);
    }

    /**
     * 제시된 토큰이 이 회원의 현재 토큰일 때만 새 토큰으로 교체하고 TTL을 다시 설정한다.
     * 이미 회전됐거나 로그아웃으로 사라진 토큰이면 아무것도 바꾸지 않고 false를 돌려준다.
     */
    public boolean rotate(Long memberId, String oldRefreshToken, String newRefreshToken, Duration ttl) {
        return SUCCESS.equals(redisTemplate.execute(
                ROTATE,
                List.of(key(memberId)),
                hash(oldRefreshToken),
                hash(newRefreshToken),
                String.valueOf(ttl.toMillis())
        ));
    }

    /**
     * 제시된 토큰이 이 회원의 현재 토큰일 때만 삭제한다.
     * 삭제했으면 true, 현재 세션과 일치하지 않아 지울 것이 없었으면 false다.
     */
    public boolean deleteIfMatches(Long memberId, String refreshToken) {
        return SUCCESS.equals(redisTemplate.execute(
                DELETE_IF_MATCHES,
                List.of(key(memberId)),
                hash(refreshToken)
        ));
    }

    /**
     * 토큰을 확인하지 않고 이 회원의 세션을 지운다. 탈퇴가 쓴다.
     *
     * <p>{@link #deleteIfMatches}와 달리 제시된 토큰과 맞는지 보지 않는다. 탈퇴는 들고 있는
     * 토큰이 무엇이든 세션을 끊어야 하고, 회원이 사라진 뒤에 남은 키는 되살릴 수도 없다.
     *
     * <p>회원당 키가 하나이므로 이 한 번으로 모든 기기의 리프레시 토큰이 사라진다.
     * 다만 <b>액세스 토큰은 즉시 폐기되지 않는다</b> — 서명과 만료만 보는 JWT라 이미 발급된
     * 것은 남은 유효 기간 동안 통과한다. 그 요청은 회원을 찾지 못해 실패한다.
     */
    public void deleteAll(Long memberId) {
        redisTemplate.delete(key(memberId));
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
