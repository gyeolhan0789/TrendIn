package com.forever102.global.security;

import com.forever102.global.exception.ErrorCode;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.stereotype.Component;

/**
 * 인증 없이 보호된 자원에 접근했을 때 401을 반환한다.
 * 토큰이 만료됐거나 잘못된 경우에는 필터가 남긴 사유를 그대로 내려준다.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final ErrorResponseWriter errorResponseWriter;

    @Override
    public void commence(
            HttpServletRequest request,
            HttpServletResponse response,
            AuthenticationException authException
    ) throws IOException {
        ErrorCode errorCode = JwtAuthenticationFilter.resolveErrorCode(request, ErrorCode.UNAUTHORIZED);
        log.debug("인증 실패 : {} {} - {}", request.getMethod(), request.getRequestURI(), errorCode.getMessage());
        errorResponseWriter.write(response, errorCode);
    }
}
