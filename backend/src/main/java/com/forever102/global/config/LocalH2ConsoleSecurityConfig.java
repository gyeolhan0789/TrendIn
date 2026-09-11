package com.forever102.global.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;

/**
 * local 프로필에서만 H2 콘솔을 인증 없이 연다.
 *
 * <p>공용 SecurityConfig의 허용 목록에 넣지 않고 별도 체인으로 분리했다.
 * 그래야 dev·운영 설정에는 이 규칙이 아예 존재하지 않는다.
 * 이 체인은 /h2-console 경로에만 적용되고 나머지 요청은 기존 체인이 그대로 처리한다.
 */
@Configuration
@Profile("local")
public class LocalH2ConsoleSecurityConfig {

    private static final String H2_CONSOLE_PATH = "/h2-console/**";

    @Bean
    @Order(Ordered.HIGHEST_PRECEDENCE)
    public SecurityFilterChain h2ConsoleSecurityFilterChain(HttpSecurity http) throws Exception {
        return http
                .securityMatcher(H2_CONSOLE_PATH)
                .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())
                .csrf(AbstractHttpConfigurer::disable)
                // H2 콘솔은 화면을 frame으로 구성하므로 같은 출처의 frame을 허용해야 한다.
                .headers(headers -> headers.frameOptions(frame -> frame.sameOrigin()))
                .build();
    }
}
