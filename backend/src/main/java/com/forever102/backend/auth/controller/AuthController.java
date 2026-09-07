package com.forever102.backend.auth.controller;

import com.forever102.backend.auth.dto.LoginRequest;
import com.forever102.backend.auth.dto.LoginResponse;
import com.forever102.backend.auth.dto.ReissueRequest;
import com.forever102.backend.auth.dto.ReissueResponse;
import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.auth.service.AuthService;
import com.forever102.backend.global.response.BaseResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
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

    @PostMapping("/signup")
    @ResponseStatus(HttpStatus.CREATED)
    public BaseResponse<SignUpResponse> signUp(@Valid @RequestBody SignUpRequest request) {
        return BaseResponse.success(authService.signUp(request));
    }

    @PostMapping("/login")
    public BaseResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return BaseResponse.success(authService.login(request));
    }

    @PostMapping("/reissue")
    public BaseResponse<ReissueResponse> reissue(@Valid @RequestBody ReissueRequest request) {
        return BaseResponse.success(authService.reissue(request));
    }
}
