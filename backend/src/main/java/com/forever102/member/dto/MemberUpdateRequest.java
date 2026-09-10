package com.forever102.member.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record MemberUpdateRequest(

        @NotBlank(message = "닉네임은 필수입니다.")
        @Size(min = 2, max = 30, message = "닉네임은 2자 이상 30자 이하여야 합니다.")
        String nickname
) {

    public MemberUpdateRequest {
        nickname = nickname == null ? null : nickname.strip();
    }
}
