package com.forever102.backend.global.config;

import com.forever102.backend.auth.jwt.JwtProperties;
import com.forever102.backend.auth.jwt.JwtTokenProvider;
import com.forever102.backend.global.security.ErrorResponseWriter;
import com.forever102.backend.global.security.JwtAccessDeniedHandler;
import com.forever102.backend.global.security.JwtAuthenticationEntryPoint;
import com.forever102.backend.global.security.JwtAuthenticationFilter;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Import;

/**
 * @WebMvcTest 슬라이스는 @Component를 스캔하지 않으므로 SecurityConfig가 필요로 하는
 * 인증 필터와 예외 핸들러를 함께 등록한다. 컨트롤러 테스트에서 SecurityConfig 대신 이 설정을 import한다.
 */
@TestConfiguration
@Import({
        SecurityConfig.class,
        JwtAuthenticationFilter.class,
        JwtAuthenticationEntryPoint.class,
        JwtAccessDeniedHandler.class,
        ErrorResponseWriter.class,
        JwtTokenProvider.class
})
@EnableConfigurationProperties(JwtProperties.class)
public class SecurityTestConfig {
}
