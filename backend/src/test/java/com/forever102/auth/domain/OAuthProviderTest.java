package com.forever102.auth.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class OAuthProviderTest {

    @Test
    @DisplayName("대소문자와 앞뒤 공백을 가리지 않고 제공자를 찾는다")
    void findsProviderCaseInsensitively() {
        assertThat(OAuthProvider.from("  GitLab  ")).contains(OAuthProvider.GITLAB);
        assertThat(OAuthProvider.from("gitlab")).contains(OAuthProvider.GITLAB);
        assertThat(OAuthProvider.from("GITLAB")).contains(OAuthProvider.GITLAB);
    }

    @Test
    @DisplayName("정의되지 않은 제공자는 비어 있는 결과를 돌려준다")
    void returnsEmptyForUnknownProvider() {
        assertThat(OAuthProvider.from("github")).isEmpty();
        assertThat(OAuthProvider.from("google")).isEmpty();
    }

    @Test
    @DisplayName("null과 공백은 비어 있는 결과를 돌려준다")
    void returnsEmptyForBlank() {
        assertThat(OAuthProvider.from(null)).isEmpty();
        assertThat(OAuthProvider.from("   ")).isEmpty();
    }
}
