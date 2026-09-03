package com.forever102.backend.auth.dto;

import com.forever102.backend.member.domain.Member;

public record SignUpResponse(
        Long memberId,
        String email,
        String nickname,
        boolean onboardingCompleted
) {

    public static SignUpResponse from(Member member) {
        return new SignUpResponse(
                member.getId(),
                member.getEmail(),
                member.getNickname(),
                member.isOnboardingCompleted()
        );
    }
}
