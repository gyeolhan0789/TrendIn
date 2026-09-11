package com.forever102.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.util.Locale;

public record EmailCheckRequest(

        @NotBlank(message = "이메일은 필수입니다.")
        @Email(message = "이메일 형식이 올바르지 않습니다.")
        @Size(max = 254, message = "이메일은 254자 이하여야 합니다.")
        String email
) {

    public EmailCheckRequest {
        // 회원가입과 같은 값으로 조회해야 확인 결과와 실제 가입 결과가 어긋나지 않는다.
        email = email == null ? null : email.strip().toLowerCase(Locale.ROOT);
    }
}
