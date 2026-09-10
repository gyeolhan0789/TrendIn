package com.forever102.member.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record SavedTrendRegisterRequest(
        @NotNull(message = "트렌드 ID는 필수입니다.")
        @Positive(message = "트렌드 ID는 양수여야 합니다.")
        Long trendId
) {
}
