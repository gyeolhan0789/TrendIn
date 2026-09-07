package com.forever102.backend.global.security;

import com.forever102.backend.auth.jwt.JwtTokenProvider;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.jspecify.annotations.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Authorization 헤더의 액세스 토큰을 검증해 SecurityContext에 인증을 채운다.
 * principal은 토큰 subject에서 꺼낸 회원 식별자(Long)이며, 요청마다 DB를 조회하지 않는다.
 * 토큰이 없거나 잘못됐어도 여기서 응답을 만들지 않고 체인을 이어간다.
 * 실제 401/403 응답은 permitAll 여부를 아는 {@link JwtAuthenticationEntryPoint}와
 * {@link JwtAccessDeniedHandler}가 만든다.
 */
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    /** 인증 실패 사유를 EntryPoint에 넘기기 위한 요청 속성 키. */
    public static final String ERROR_CODE_ATTRIBUTE = JwtAuthenticationFilter.class.getName() + ".errorCode";

    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtTokenProvider jwtTokenProvider;
    private final WebAuthenticationDetailsSource detailsSource = new WebAuthenticationDetailsSource();

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain
    ) throws ServletException, IOException {
        String token = resolveToken(request);
        if (token != null && SecurityContextHolder.getContext().getAuthentication() == null) {
            authenticate(request, token);
        }
        filterChain.doFilter(request, response);
    }

    private void authenticate(HttpServletRequest request, String token) {
        try {
            Long memberId = jwtTokenProvider.parseAccessToken(token);
            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(memberId, null, List.of());
            authentication.setDetails(detailsSource.buildDetails(request));
            SecurityContextHolder.getContext().setAuthentication(authentication);
        } catch (BusinessException e) {
            // 인증 없이 통과시키고, 보호된 자원이면 EntryPoint가 이 사유로 401을 만든다.
            SecurityContextHolder.clearContext();
            request.setAttribute(ERROR_CODE_ATTRIBUTE, e.getErrorCode());
        }
    }

    private String resolveToken(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header == null || !header.startsWith(BEARER_PREFIX)) {
            return null;
        }
        String token = header.substring(BEARER_PREFIX.length()).trim();
        return token.isEmpty() ? null : token;
    }

    static ErrorCode resolveErrorCode(HttpServletRequest request, ErrorCode defaultErrorCode) {
        Object errorCode = request.getAttribute(ERROR_CODE_ATTRIBUTE);
        return errorCode instanceof ErrorCode found ? found : defaultErrorCode;
    }
}
