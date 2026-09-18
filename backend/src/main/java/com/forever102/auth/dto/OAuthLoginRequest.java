package com.forever102.auth.dto;

import jakarta.validation.constraints.NotBlank;

public record OAuthLoginRequest(

        @NotBlank(message = "인가 코드는 필수입니다.")
        String code,

        @NotBlank(message = "state는 필수입니다.")
        String state
) {

    public OAuthLoginRequest {
        code = code == null ? null : code.strip();
        state = state == null ? null : state.strip();
    }
}
