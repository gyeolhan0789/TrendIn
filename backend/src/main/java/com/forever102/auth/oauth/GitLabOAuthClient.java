package com.forever102.auth.oauth;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * GitLab OAuth 제공자와 통신한다.
 *
 * <p>실패를 두 갈래로 나눈다. 제공자가 4xx로 답하면 코드가 이미 쓰였거나 만료된 것이라
 * 사용자 쪽 인증 실패(401)로 보고, 응답이 5xx이거나 아예 닿지 못하면 제공자 장애(502)로 본다.
 * 둘을 합치면 프런트가 재시도해야 할 상황과 다시 로그인해야 할 상황을 구분하지 못한다.
 */
@Component
@Slf4j
public class GitLabOAuthClient {

    private static final String GRANT_TYPE = "authorization_code";

    private final RestClient restClient;
    private final GitLabProperties properties;

    public GitLabOAuthClient(RestClient oauthRestClient, GitLabProperties properties) {
        this.restClient = oauthRestClient;
        this.properties = properties;
        warnIfNotConfigured();
    }

    /**
     * 자격증명이 비면 제공자가 4xx로 답해 인증 실패(401)처럼 보인다.
     * 설정 누락과 실제 인증 실패를 구분할 수 있도록 기동 시점에 남긴다.
     */
    private void warnIfNotConfigured() {
        if (properties.clientId().isEmpty() || properties.clientSecret().isEmpty()) {
            log.warn("GitLab OAuth 자격증명이 비어 있다. "
                    + "GITLAB_OAUTH_CLIENT_ID와 GITLAB_OAUTH_CLIENT_SECRET을 설정하기 전까지 OAuth 로그인은 실패한다.");
        }
        if (properties.redirectUri().isEmpty()) {
            log.warn("GitLab OAuth redirect-uri가 비어 있다. "
                    + "제공자에 등록한 값과 같게 GITLAB_OAUTH_REDIRECT_URI를 설정해야 한다.");
        }
    }

    /**
     * 일회용 인가 코드를 액세스 토큰으로 교환한 뒤 사용자 정보를 읽어온다.
     */
    public OAuthUserInfo fetchUserInfo(String code) {
        String accessToken = exchangeCode(code);
        return readUser(accessToken);
    }

    private String exchangeCode(String code) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", GRANT_TYPE);
        form.add("code", code);
        form.add("client_id", properties.clientId());
        form.add("client_secret", properties.clientSecret());
        form.add("redirect_uri", properties.redirectUri());

        Map<String, Object> body = call(() -> restClient.post()
                .uri(properties.tokenUri())
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(form)
                .retrieve()
                .onStatus(status -> status.is4xxClientError(), (request, response) -> {
                    // 코드가 이미 소모됐거나 redirect_uri가 등록값과 다른 경우다.
                    log.info("GitLab 토큰 교환 거절 : status={}", response.getStatusCode());
                    throw new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED);
                })
                .body(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {
                }));

        Object accessToken = body == null ? null : body.get("access_token");
        if (!(accessToken instanceof String token) || token.isBlank()) {
            log.warn("GitLab 토큰 응답에 access_token이 없다.");
            throw new BusinessException(ErrorCode.OAUTH_PROVIDER_ERROR);
        }
        return token;
    }

    private OAuthUserInfo readUser(String accessToken) {
        Map<String, Object> body = call(() -> restClient.get()
                .uri(properties.userUri())
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken)
                .retrieve()
                .onStatus(status -> status.is4xxClientError(), (request, response) -> {
                    log.info("GitLab 사용자 조회 거절 : status={}", response.getStatusCode());
                    throw new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED);
                })
                .body(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {
                }));

        if (body == null || body.get("id") == null) {
            log.warn("GitLab 사용자 응답에 id가 없다.");
            throw new BusinessException(ErrorCode.OAUTH_PROVIDER_ERROR);
        }
        return new OAuthUserInfo(
                String.valueOf(body.get("id")),
                asText(body.get("email")),
                firstNonBlank(asText(body.get("name")), asText(body.get("username"))));
    }

    /**
     * 5xx와 연결 실패를 제공자 장애로 묶는다.
     * 인증 실패로 이미 판정한 BusinessException은 그대로 통과시킨다.
     */
    private <T> T call(java.util.function.Supplier<T> request) {
        try {
            return request.get();
        } catch (BusinessException e) {
            throw e;
        } catch (RestClientException e) {
            log.warn("GitLab 통신 실패", e);
            throw new BusinessException(ErrorCode.OAUTH_PROVIDER_ERROR);
        }
    }

    private String asText(Object value) {
        return value instanceof String text && !text.isBlank() ? text.strip() : null;
    }

    private String firstNonBlank(String first, String second) {
        return first != null ? first : second;
    }
}
