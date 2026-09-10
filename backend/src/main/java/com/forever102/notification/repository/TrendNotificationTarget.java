package com.forever102.notification.repository;

import com.forever102.member.domain.Member;
import com.forever102.member.domain.MemberInterestKeyword;
import com.forever102.trend.domain.Trend;

public record TrendNotificationTarget(
        MemberInterestKeyword interestKeyword,
        Member member,
        Trend trend,
        String keyword
) {
}
