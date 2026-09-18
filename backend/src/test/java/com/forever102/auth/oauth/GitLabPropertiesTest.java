package com.forever102.auth.oauth;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class GitLabPropertiesTest {

    @Test
    @DisplayName("base-url 뒤의 슬래시를 정리해 엔드포인트가 겹치지 않게 한다")
    void stripsTrailingSlash() {
        GitLabProperties properties =
                new GitLabProperties("https://lab.ssafy.com/", "id", "secret", "https://app/cb");

        assertThat(properties.tokenUri()).isEqualTo("https://lab.ssafy.com/oauth/token");
        assertThat(properties.userUri()).isEqualTo("https://lab.ssafy.com/api/v4/user");
    }

    @Test
    @DisplayName("슬래시가 없는 base-url도 같은 엔드포인트를 만든다")
    void buildsSameUriWithoutTrailingSlash() {
        GitLabProperties properties =
                new GitLabProperties("https://gitlab.com", "id", "secret", "https://app/cb");

        assertThat(properties.tokenUri()).isEqualTo("https://gitlab.com/oauth/token");
        assertThat(properties.userUri()).isEqualTo("https://gitlab.com/api/v4/user");
    }

    @Test
    @DisplayName("설정이 비어 있어도 객체 생성은 실패하지 않는다")
    void allowsMissingCredentials() {
        GitLabProperties properties = new GitLabProperties(null, null, null, null);

        assertThat(properties.clientId()).isEmpty();
        assertThat(properties.clientSecret()).isEmpty();
        assertThat(properties.redirectUri()).isEmpty();
    }
}
