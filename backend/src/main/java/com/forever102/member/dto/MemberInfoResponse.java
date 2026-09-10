package com.forever102.member.dto;

import com.forever102.member.domain.Member;

public record MemberInfoResponse(
        Long memberId,
        String email,
        String nickname,
        boolean onboardingCompleted
) {

    public static MemberInfoResponse from(Member member) {
        return new MemberInfoResponse(
                member.getId(),
                member.getEmail(),
                member.getNickname(),
                member.isOnboardingCompleted()
        );
    }
}
