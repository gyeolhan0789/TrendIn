package com.forever102.member.dto;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.MemberInterestKeyword;

public record InterestKeywordResponse(
        Long interestKeywordId,
        Long keywordId,
        String keyword,
        Domain domain
) {
    public static InterestKeywordResponse from(MemberInterestKeyword interestKeyword) {
        return new InterestKeywordResponse(
                interestKeyword.getId(),
                interestKeyword.getKeyword().getId(),
                interestKeyword.getKeyword().getName(),
                interestKeyword.getKeyword().getDomain());
    }
}
