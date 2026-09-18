package com.forever102.auth.controller;

import com.forever102.auth.dto.EmailCheckRequest;
import com.forever102.auth.dto.EmailCheckResponse;
import com.forever102.auth.dto.LoginRequest;
import com.forever102.auth.dto.LoginResponse;
import com.forever102.auth.dto.OAuthLoginRequest;
import com.forever102.auth.dto.OAuthLoginResponse;
import com.forever102.auth.dto.LogoutRequest;
import com.forever102.auth.dto.ReissueRequest;
import com.forever102.auth.dto.ReissueResponse;
import com.forever102.auth.dto.SignUpRequest;
import com.forever102.auth.dto.SignUpResponse;
import com.forever102.auth.service.AuthService;
import com.forever102.auth.service.OAuthService;
import com.forever102.global.response.BaseResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;
    private final OAuthService oauthService;

    @PostMapping("/signup")
    @ResponseStatus(HttpStatus.CREATED)
    public BaseResponse<SignUpResponse> signUp(@Valid @RequestBody SignUpRequest request) {
        return BaseResponse.success(authService.signUp(request));
    }

    @PostMapping("/email-check")
    public BaseResponse<EmailCheckResponse> checkEmail(@Valid @RequestBody EmailCheckRequest request) {
        return BaseResponse.success(authService.checkEmail(request));
    }

    @PostMapping("/login")
    public BaseResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return BaseResponse.success(authService.login(request));
    }


    @PostMapping("/oauth/{provider}/login")
    public BaseResponse<OAuthLoginResponse> oauthLogin(
            @PathVariable String provider,
            @Valid @RequestBody OAuthLoginRequest request
    ) {
        return BaseResponse.success(oauthService.login(provider, request));
    }

    @PostMapping("/reissue")
    public BaseResponse<ReissueResponse> reissue(@Valid @RequestBody ReissueRequest request) {
        return BaseResponse.success(authService.reissue(request));
    }

    @PostMapping("/logout")
    public BaseResponse<Void> logout(
            @AuthenticationPrincipal Long memberId,
            @Valid @RequestBody LogoutRequest request
    ) {
        authService.logout(memberId, request);
        return BaseResponse.success(null);
    }
}
