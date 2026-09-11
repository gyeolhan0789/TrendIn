package com.forever102.auth.dto;

public record EmailCheckResponse(
        boolean available
) {

    public static EmailCheckResponse of(boolean available) {
        return new EmailCheckResponse(available);
    }
}
