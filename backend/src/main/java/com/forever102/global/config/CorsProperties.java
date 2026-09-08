package com.forever102.global.config;

import java.time.Duration;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 프런트엔드 오리진은 환경마다 다르므로 설정으로 주입받는다.
 * 인증 헤더를 함께 보내므로 와일드카드(*) 오리진은 허용하지 않는다.
 */
@ConfigurationProperties(prefix = "cors")
public record CorsProperties(
        List<String> allowedOrigins,
        List<String> allowedMethods,
        List<String> exposedHeaders,
        Duration maxAge
) {

    private static final List<String> DEFAULT_METHODS =
            List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS");
    private static final Duration DEFAULT_MAX_AGE = Duration.ofHours(1);

    public CorsProperties {
        allowedOrigins = allowedOrigins == null ? List.of() : List.copyOf(allowedOrigins);
        allowedMethods = allowedMethods == null || allowedMethods.isEmpty()
                ? DEFAULT_METHODS : List.copyOf(allowedMethods);
        exposedHeaders = exposedHeaders == null ? List.of() : List.copyOf(exposedHeaders);
        maxAge = maxAge == null ? DEFAULT_MAX_AGE : maxAge;
    }
}
