package com.forever102.backend.auth.jwt;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Date;
import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class JwtTokenProviderTest {

    private static final String SECRET = "trendin-test-secret-key-that-is-long-enough-for-hs256";
    private static final Duration ACCESS_TOKEN_EXPIRATION = Duration.ofMinutes(15);
    private static final Duration REFRESH_TOKEN_EXPIRATION = Duration.ofDays(14);
    private static final Long MEMBER_ID = 1L;

    private final JwtTokenProvider jwtTokenProvider = new JwtTokenProvider(
            new JwtProperties(SECRET, ACCESS_TOKEN_EXPIRATION, REFRESH_TOKEN_EXPIRATION)
    );

    @Test
    @DisplayName("발급한 토큰의 만료 시간은 설정된 값을 초 단위로 그대로 반환한다")
    void issueReturnsConfiguredExpiration() {
        // when
        AuthTokens tokens = jwtTokenProvider.issue(MEMBER_ID);

        // then
        assertThat(tokens.accessTokenExpiresIn()).isEqualTo(900L);
        assertThat(tokens.refreshTokenExpiresIn()).isEqualTo(1_209_600L);
    }

    @Test
    @DisplayName("액세스 토큰의 subject는 회원 식별자이고 타입은 access다")
    void accessTokenCarriesMemberIdAndType() {
        // when
        Claims claims = parse(jwtTokenProvider.issue(MEMBER_ID).accessToken());

        // then
        assertThat(claims.getSubject()).isEqualTo("1");
        assertThat(claims.get(JwtTokenProvider.TOKEN_TYPE_CLAIM))
                .isEqualTo(JwtTokenProvider.ACCESS_TOKEN_TYPE);
    }

    @Test
    @DisplayName("리프레시 토큰의 타입은 refresh다")
    void refreshTokenCarriesRefreshType() {
        // when
        Claims claims = parse(jwtTokenProvider.issue(MEMBER_ID).refreshToken());

        // then
        assertThat(claims.get(JwtTokenProvider.TOKEN_TYPE_CLAIM))
                .isEqualTo(JwtTokenProvider.REFRESH_TOKEN_TYPE);
    }

    @Test
    @DisplayName("리프레시 토큰이 액세스 토큰보다 늦게 만료된다")
    void refreshTokenOutlivesAccessToken() {
        // when
        AuthTokens tokens = jwtTokenProvider.issue(MEMBER_ID);

        // then
        Date accessExpiration = parse(tokens.accessToken()).getExpiration();
        Date refreshExpiration = parse(tokens.refreshToken()).getExpiration();
        assertThat(refreshExpiration).isAfter(accessExpiration);
    }

    @Test
    @DisplayName("같은 회원에게 발급해도 액세스 토큰과 리프레시 토큰은 서로 다르다")
    void issuesDistinctTokens() {
        // when
        AuthTokens tokens = jwtTokenProvider.issue(MEMBER_ID);

        // then
        assertThat(tokens.accessToken()).isNotEqualTo(tokens.refreshToken());
    }

    @Test
    @DisplayName("다른 키로 서명된 토큰은 검증에 실패한다")
    void rejectsTokenSignedWithAnotherKey() {
        // given
        String token = jwtTokenProvider.issue(MEMBER_ID).accessToken();
        SecretKey otherKey = new SecretKeySpec(
                "another-secret-key-that-is-also-long-enough-1234".getBytes(StandardCharsets.UTF_8), "HmacSHA256"
        );

        // when & then
        assertThatThrownBy(() -> Jwts.parser().verifyWith(otherKey).build().parseSignedClaims(token))
                .isInstanceOf(io.jsonwebtoken.security.SignatureException.class);
    }

    @Test
    @DisplayName("시크릿이 32바이트 미만이면 생성에 실패한다")
    void rejectsTooShortSecret() {
        // given
        JwtProperties properties = new JwtProperties("too-short", ACCESS_TOKEN_EXPIRATION, REFRESH_TOKEN_EXPIRATION);

        // when & then
        assertThatThrownBy(() -> new JwtTokenProvider(properties))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32바이트");
    }

    @Test
    @DisplayName("시크릿 길이와 무관하게 HS256으로 서명한다")
    void signsWithHs256RegardlessOfSecretLength() {
        // given
        String longerSecret = SECRET + "-with-extra-bytes-that-would-otherwise-select-hs512";
        JwtTokenProvider provider = new JwtTokenProvider(
                new JwtProperties(longerSecret, ACCESS_TOKEN_EXPIRATION, REFRESH_TOKEN_EXPIRATION)
        );

        // when
        String header = provider.issue(MEMBER_ID).accessToken().split("\\.")[0];

        // then
        assertThat(new String(Base64.getUrlDecoder().decode(header), StandardCharsets.UTF_8))
                .contains("\"HS256\"");
    }

    @Test
    @DisplayName("리프레시 토큰의 TTL은 만료 시간과 같다")
    void refreshTokenTtlMatchesExpiration() {
        // when
        AuthTokens tokens = jwtTokenProvider.issue(MEMBER_ID);

        // then
        assertThat(tokens.refreshTokenTtl()).isEqualTo(REFRESH_TOKEN_EXPIRATION);
    }

    @Test
    @DisplayName("액세스 토큰을 파싱하면 회원 식별자를 돌려준다")
    void parsesMemberIdFromAccessToken() {
        // given
        String accessToken = jwtTokenProvider.issue(MEMBER_ID).accessToken();

        // when & then
        assertThat(jwtTokenProvider.parseAccessToken(accessToken)).isEqualTo(MEMBER_ID);
    }

    @Test
    @DisplayName("리프레시 토큰으로는 액세스 토큰 파싱에 실패한다")
    void rejectsRefreshTokenAsAccessToken() {
        // given
        String refreshToken = jwtTokenProvider.issue(MEMBER_ID).refreshToken();

        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseAccessToken(refreshToken))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_TOKEN);
    }

    @Test
    @DisplayName("만료된 토큰은 EXPIRED_TOKEN으로 구분한다")
    void rejectsExpiredToken() {
        // given
        JwtTokenProvider expiredProvider = new JwtTokenProvider(
                new JwtProperties(SECRET, Duration.ofSeconds(-1), REFRESH_TOKEN_EXPIRATION)
        );
        String expiredToken = expiredProvider.issue(MEMBER_ID).accessToken();

        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseAccessToken(expiredToken))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.EXPIRED_TOKEN);
    }

    @Test
    @DisplayName("다른 키로 서명된 토큰은 INVALID_TOKEN으로 거부한다")
    void rejectsTokenSignedWithAnotherKeyOnParse() {
        // given
        JwtTokenProvider otherProvider = new JwtTokenProvider(new JwtProperties(
                "another-secret-key-that-is-also-long-enough-1234",
                ACCESS_TOKEN_EXPIRATION,
                REFRESH_TOKEN_EXPIRATION
        ));
        String foreignToken = otherProvider.issue(MEMBER_ID).accessToken();

        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseAccessToken(foreignToken))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_TOKEN);
    }

    @Test
    @DisplayName("JWT 형식이 아닌 문자열은 INVALID_TOKEN으로 거부한다")
    void rejectsMalformedToken() {
        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseAccessToken("not-a-jwt"))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_TOKEN);
    }

    @Test
    @DisplayName("리프레시 토큰을 파싱하면 회원 식별자를 돌려준다")
    void parsesMemberIdFromRefreshToken() {
        // given
        String refreshToken = jwtTokenProvider.issue(MEMBER_ID).refreshToken();

        // when & then
        assertThat(jwtTokenProvider.parseRefreshToken(refreshToken)).isEqualTo(MEMBER_ID);
    }

    @Test
    @DisplayName("액세스 토큰으로는 리프레시 토큰 파싱에 실패한다")
    void rejectsAccessTokenAsRefreshToken() {
        // given
        String accessToken = jwtTokenProvider.issue(MEMBER_ID).accessToken();

        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseRefreshToken(accessToken))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("만료된 리프레시 토큰도 무효와 같은 INVALID_REFRESH_TOKEN으로 거부한다")
    void rejectsExpiredRefreshTokenWithSameErrorCode() {
        // given
        JwtTokenProvider expiredProvider = new JwtTokenProvider(
                new JwtProperties(SECRET, ACCESS_TOKEN_EXPIRATION, Duration.ofSeconds(-1))
        );
        String expiredToken = expiredProvider.issue(MEMBER_ID).refreshToken();

        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseRefreshToken(expiredToken))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_REFRESH_TOKEN);
    }

    @Test
    @DisplayName("JWT 형식이 아닌 리프레시 토큰은 INVALID_REFRESH_TOKEN으로 거부한다")
    void rejectsMalformedRefreshToken() {
        // when & then
        assertThatThrownBy(() -> jwtTokenProvider.parseRefreshToken("not-a-jwt"))
                .isInstanceOf(BusinessException.class)
                .extracting(exception -> ((BusinessException) exception).getErrorCode())
                .isEqualTo(ErrorCode.INVALID_REFRESH_TOKEN);
    }
    private Claims parse(String token) {
        SecretKey key = new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}
