package com.forever102.backend.global.response;

public record ErrorResponse(
        boolean success,
        String message
) {

    public static ErrorResponse of(String message) {
        return new ErrorResponse(false, message);
    }
}
