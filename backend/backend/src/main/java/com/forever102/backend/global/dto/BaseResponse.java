package com.forever102.backend.global.dto;

import lombok.Builder;

@Builder
public record BaseResponse<T>(
        boolean success,
        T data,
        String message
) {
    public static <T> BaseResponse<T> success(T data) {
        return new BaseResponse<>(true, data, null);
    }

    public static <T> BaseResponse<T> fail(String message) {
        return new BaseResponse<>(false, null, message);
    }

}
