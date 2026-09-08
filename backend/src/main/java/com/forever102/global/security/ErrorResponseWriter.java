package com.forever102.global.security;

import tools.jackson.databind.ObjectMapper;
import com.forever102.global.exception.ErrorCode;
import com.forever102.global.response.ErrorResponse;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

/**
 * 필터 단계에서 발생한 오류를 컨트롤러와 같은 ErrorResponse 형식으로 내려준다.
 * 이 시점에는 @RestControllerAdvice가 동작하지 않아 응답을 직접 쓴다.
 */
@Component
@RequiredArgsConstructor
public class ErrorResponseWriter {

    private final ObjectMapper objectMapper;

    public void write(HttpServletResponse response, ErrorCode errorCode) throws IOException {
        response.setStatus(errorCode.getStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(response.getWriter(), ErrorResponse.of(errorCode.getMessage()));
    }
}
