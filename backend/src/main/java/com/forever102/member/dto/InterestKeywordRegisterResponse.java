package com.forever102.member.dto;

import com.forever102.member.domain.MemberInterestKeyword;

public record InterestKeywordRegisterResponse(
        Long interestKeywordId,
        Long keywordId,
        String keyword
) {
    public static InterestKeywordRegisterResponse from(MemberInterestKeyword interestKeyword) {
        return new InterestKeywordRegisterResponse(
                interestKeyword.getId(),
                interestKeyword.getKeyword().getId(),
                interestKeyword.getKeyword().getName());
    }
}
