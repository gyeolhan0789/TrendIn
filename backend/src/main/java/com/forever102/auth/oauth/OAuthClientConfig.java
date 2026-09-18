package com.forever102.auth.oauth;

import java.time.Duration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

/**
 * OAuth 제공자 호출용 HTTP 클라이언트.
 *
 * <p>자동 구성 빌더를 주입받지 않고 직접 만든다. 타임아웃을 반드시 걸어야 하기 때문이다.
 * 제공자가 응답하지 않을 때 기본값(무제한)이면 로그인 요청 스레드가 그대로 묶인다.
 */
@Configuration
public class OAuthClientConfig {

    private static final Duration CONNECT_TIMEOUT = Duration.ofSeconds(3);
    private static final Duration READ_TIMEOUT = Duration.ofSeconds(5);

    @Bean
    public RestClient oauthRestClient() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(CONNECT_TIMEOUT);
        factory.setReadTimeout(READ_TIMEOUT);
        return RestClient.builder()
                .requestFactory(factory)
                .build();
    }
}
