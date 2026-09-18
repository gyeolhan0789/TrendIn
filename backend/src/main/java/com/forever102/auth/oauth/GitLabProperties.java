package com.forever102.auth.oauth;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * GitLab OAuth 설정.
 *
 * <p>인스턴스마다 주소가 달라 base-url을 설정으로 받는다. 사내 GitLab과 gitlab.com 모두 같은
 * 엔드포인트 규약을 쓰므로 주소만 바꾸면 동작한다.
 *
 * <p>client-id와 client-secret은 기본값을 비워 둔다. 값이 없어도 애플리케이션은 떠야 하고,
 * OAuth 로그인을 실제로 호출할 때만 제공자 통신이 실패한다.
 */
@ConfigurationProperties(prefix = "oauth.gitlab")
public record GitLabProperties(
        String baseUrl,
        String clientId,
        String clientSecret,
        String redirectUri
) {

    public GitLabProperties {
        baseUrl = baseUrl == null ? "" : stripTrailingSlash(baseUrl.strip());
        clientId = clientId == null ? "" : clientId.strip();
        clientSecret = clientSecret == null ? "" : clientSecret.strip();
        redirectUri = redirectUri == null ? "" : redirectUri.strip();
    }

    public String tokenUri() {
        return baseUrl + "/oauth/token";
    }

    public String userUri() {
        return baseUrl + "/api/v4/user";
    }

    private static String stripTrailingSlash(String value) {
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }
}
