package com.forever102.member.domain;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@RequiredArgsConstructor
@Getter
public enum Domain {
    DEVELOP("개발"),
    FASHION("패션");

    private final String name;
}
