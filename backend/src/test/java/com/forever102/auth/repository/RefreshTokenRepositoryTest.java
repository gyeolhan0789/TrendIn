package com.forever102.auth.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;

/**
 * Lua 스크립트 자체의 동작은 실제 Redis가 있어야 확인할 수 있으므로,
 * 여기서는 스크립트에 넘기는 키·인자와 반환값 해석이 맞는지를 검증한다.
 */
@ExtendWith(MockitoExtension.class)
class RefreshTokenRepositoryTest {

    private static final Long MEMBER_ID = 1L;
    private static final String KEY = "refresh:member:1";
    private static final String OLD_TOKEN = "old-refresh-token";
    private static final String NEW_TOKEN = "new-refresh-token";
    private static final Duration TTL = Duration.ofDays(14);
    private static final String OLD_TOKEN_HASH = "66e4f4e9739a9ef9a9d6e414cfd05780c4ab0eb03e21fbf90ebf87e76d4db8f6";
    private static final String NEW_TOKEN_HASH = "c40dd1765d767caae2588f0ee1de9181d8a44cc9306261eb2c9e526351188338";

    @Mock
    private StringRedisTemplate redisTemplate;

    @InjectMocks
    private RefreshTokenRepository refreshTokenRepository;

    @Test
    @DisplayName("교체는 회원 키에 이전·새 토큰 해시와 밀리초 TTL을 넘긴다")
    void rotatePassesHashesAndTtl() {
        // given
        givenRotateReturns(1L);

        // when
        refreshTokenRepository.rotate(MEMBER_ID, OLD_TOKEN, NEW_TOKEN, TTL);

        // then
        ArgumentCaptor<List<String>> keys = ArgumentCaptor.captor();
        ArgumentCaptor<Object> args = ArgumentCaptor.captor();
        then(redisTemplate).should().execute(
                any(), keys.capture(), args.capture(), args.capture(), args.capture());
        assertThat(keys.getValue()).containsExactly(KEY);
        assertThat(args.getAllValues()).containsExactly(
                OLD_TOKEN_HASH, NEW_TOKEN_HASH, String.valueOf(TTL.toMillis()));
    }

    @Test
    @DisplayName("교체는 토큰 원문이 아닌 SHA-256 해시를 넘긴다")
    void rotatePassesHashesNotRawTokens() {
        // given
        givenRotateReturns(1L);

        // when
        refreshTokenRepository.rotate(MEMBER_ID, OLD_TOKEN, NEW_TOKEN, TTL);

        // then
        ArgumentCaptor<Object> args = ArgumentCaptor.captor();
        then(redisTemplate).should().execute(
                any(), anyList(), args.capture(), args.capture(), args.capture());
        assertThat(args.getAllValues().subList(0, 2))
                .doesNotContain(OLD_TOKEN, NEW_TOKEN)
                .containsExactly(OLD_TOKEN_HASH, NEW_TOKEN_HASH);
    }

    @Test
    @DisplayName("교체 스크립트가 1을 반환하면 성공으로 본다")
    void rotateSucceedsWhenScriptReturnsOne() {
        // given
        givenRotateReturns(1L);

        // when & then
        assertThat(refreshTokenRepository.rotate(MEMBER_ID, OLD_TOKEN, NEW_TOKEN, TTL)).isTrue();
    }

    @Test
    @DisplayName("교체 스크립트가 0을 반환하면 현재 토큰이 아니므로 실패로 본다")
    void rotateFailsWhenScriptReturnsZero() {
        // given
        givenRotateReturns(0L);

        // when & then
        assertThat(refreshTokenRepository.rotate(MEMBER_ID, OLD_TOKEN, NEW_TOKEN, TTL)).isFalse();
    }

    @Test
    @DisplayName("교체 스크립트가 아무것도 반환하지 않아도 실패로 본다")
    void rotateFailsWhenScriptReturnsNull() {
        // given
        givenRotateReturns(null);

        // when & then
        assertThat(refreshTokenRepository.rotate(MEMBER_ID, OLD_TOKEN, NEW_TOKEN, TTL)).isFalse();
    }

    @Test
    @DisplayName("조건부 삭제는 회원 키에 토큰 해시만 넘긴다")
    void deleteIfMatchesPassesHash() {
        // given
        givenDeleteReturns(1L);

        // when
        refreshTokenRepository.deleteIfMatches(MEMBER_ID, OLD_TOKEN);

        // then
        ArgumentCaptor<List<String>> keys = ArgumentCaptor.captor();
        ArgumentCaptor<Object> args = ArgumentCaptor.captor();
        then(redisTemplate).should().execute(any(), keys.capture(), args.capture());
        assertThat(keys.getValue()).containsExactly(KEY);
        assertThat(args.getValue()).isEqualTo(OLD_TOKEN_HASH);
        assertThat((String) args.getValue()).isNotEqualTo(OLD_TOKEN);
    }

    @Test
    @DisplayName("삭제 스크립트가 1을 반환하면 삭제된 것으로 본다")
    void deleteIfMatchesSucceedsWhenScriptReturnsOne() {
        // given
        givenDeleteReturns(1L);

        // when & then
        assertThat(refreshTokenRepository.deleteIfMatches(MEMBER_ID, OLD_TOKEN)).isTrue();
    }

    @Test
    @DisplayName("삭제 스크립트가 0을 반환하면 현재 세션과 다르므로 실패로 본다")
    void deleteIfMatchesFailsWhenScriptReturnsZero() {
        // given
        givenDeleteReturns(0L);

        // when & then
        assertThat(refreshTokenRepository.deleteIfMatches(MEMBER_ID, OLD_TOKEN)).isFalse();
    }

    @Test
    @DisplayName("삭제 스크립트가 아무것도 반환하지 않아도 실패로 본다")
    void deleteIfMatchesFailsWhenScriptReturnsNull() {
        // given
        givenDeleteReturns(null);

        // when & then
        assertThat(refreshTokenRepository.deleteIfMatches(MEMBER_ID, OLD_TOKEN)).isFalse();
    }

    private void givenRotateReturns(Long result) {
        given(redisTemplate.execute(any(), anyList(), any(), any(), any()))
                .willReturn(result);
    }

    private void givenDeleteReturns(Long result) {
        given(redisTemplate.execute(any(), anyList(), any()))
                .willReturn(result);
    }
}
