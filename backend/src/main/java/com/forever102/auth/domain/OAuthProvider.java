package com.forever102.auth.domain;

import java.util.Arrays;
import java.util.Locale;
import java.util.Optional;

/**
 * 지원하는 OAuth 제공자.
 * 경로 변수로 들어온 문자열을 여기에 없는 값이면 활성화하지 않은 제공자로 본다.
 */
public enum OAuthProvider {
    GITLAB;

    public static Optional<OAuthProvider> from(String value) {
        if (value == null || value.isBlank()) {
            return Optional.empty();
        }
        String normalized = value.strip().toUpperCase(Locale.ROOT);
        return Arrays.stream(values())
                .filter(provider -> provider.name().equals(normalized))
                .findFirst();
    }
}
