package com.forever102.backend.global.config;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.backend.auth.jwt.JwtProperties;
import com.forever102.backend.auth.jwt.JwtTokenProvider;
import java.time.Duration;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@WebMvcTest(controllers = SecurityConfigTest.SecuredTestController.class)
@Import({SecurityTestConfig.class, SecurityConfigTest.SecuredTestController.class})
class SecurityConfigTest {

    private static final String SECURED_URL = "/secured";
    private static final String PUBLIC_URL = "/auth/login";
    private static final String ALLOWED_ORIGIN = "http://localhost:5173";
    private static final String DISALLOWED_ORIGIN = "https://evil.example.com";
    private static final Long MEMBER_ID = 42L;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Autowired
    private JwtProperties jwtProperties;

    @Test
    @DisplayName("유효한 액세스 토큰이면 회원 식별자를 principal로 넣어 통과시킨다")
    void authenticatesWithValidAccessToken() throws Exception {
        // given
        String accessToken = jwtTokenProvider.issue(MEMBER_ID).accessToken();

        // when & then
        mockMvc.perform(get(SECURED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
                .andExpect(status().isOk())
                .andExpect(content().string(String.valueOf(MEMBER_ID)));
    }

    @Test
    @DisplayName("토큰이 없으면 401과 인증 필요 메시지를 반환한다")
    void rejectsRequestWithoutToken() throws Exception {
        mockMvc.perform(get(SECURED_URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
    }

    @Test
    @DisplayName("Bearer 형식이 아닌 헤더는 토큰이 없는 것으로 본다")
    void rejectsNonBearerAuthorizationHeader() throws Exception {
        mockMvc.perform(get(SECURED_URL).header(HttpHeaders.AUTHORIZATION, "Basic abcdef"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
    }

    @Test
    @DisplayName("서명이 맞지 않는 토큰이면 401과 유효하지 않은 토큰 메시지를 반환한다")
    void rejectsInvalidToken() throws Exception {
        mockMvc.perform(get(SECURED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("유효하지 않은 토큰입니다."));
    }

    @Test
    @DisplayName("만료된 토큰이면 401과 만료 메시지를 반환한다")
    void rejectsExpiredToken() throws Exception {
        // given
        JwtTokenProvider expiredProvider = new JwtTokenProvider(new JwtProperties(
                jwtProperties.secret(), Duration.ofSeconds(-1), jwtProperties.refreshTokenExpiration()));
        String expiredToken = expiredProvider.issue(MEMBER_ID).accessToken();

        // when & then
        mockMvc.perform(get(SECURED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + expiredToken))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("만료된 토큰입니다."));
    }

    @Test
    @DisplayName("리프레시 토큰으로 API를 호출하면 401을 반환한다")
    void rejectsRefreshTokenOnApiCall() throws Exception {
        // given
        String refreshToken = jwtTokenProvider.issue(MEMBER_ID).refreshToken();

        // when & then
        mockMvc.perform(get(SECURED_URL).header(HttpHeaders.AUTHORIZATION, "Bearer " + refreshToken))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("유효하지 않은 토큰입니다."));
    }

    @Test
    @DisplayName("로그인 엔드포인트는 토큰 없이 접근할 수 있다")
    void allowsPublicEndpointWithoutToken() throws Exception {
        mockMvc.perform(post(PUBLIC_URL))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("허용된 오리진의 프리플라이트는 토큰 없이 통과한다")
    void allowsPreflightFromAllowedOrigin() throws Exception {
        mockMvc.perform(options(SECURED_URL)
                        .header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, HttpHeaders.AUTHORIZATION))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN));
    }

    @Test
    @DisplayName("허용하지 않은 오리진의 프리플라이트는 거부한다")
    void rejectsPreflightFromDisallowedOrigin() throws Exception {
        mockMvc.perform(options(SECURED_URL)
                        .header(HttpHeaders.ORIGIN, DISALLOWED_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET"))
                .andExpect(status().isForbidden())
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    @Test
    @DisplayName("허용된 오리진의 실제 요청에는 CORS 허용 헤더를 붙인다")
    void addsCorsHeaderToActualRequest() throws Exception {
        // given
        String accessToken = jwtTokenProvider.issue(MEMBER_ID).accessToken();

        // when & then
        mockMvc.perform(get(SECURED_URL)
                        .header(HttpHeaders.ORIGIN, ALLOWED_ORIGIN)
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ALLOWED_ORIGIN))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_CREDENTIALS));
    }

    @RestController
    static class SecuredTestController {

        @GetMapping(SECURED_URL)
        String secured(@AuthenticationPrincipal Long memberId) {
            return String.valueOf(memberId);
        }

        @PostMapping(PUBLIC_URL)
        String publicEndpoint() {
            return "ok";
        }
    }
}
