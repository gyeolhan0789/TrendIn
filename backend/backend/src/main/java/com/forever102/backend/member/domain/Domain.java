package com.forever102.backend.member.domain;

import lombok.RequiredArgsConstructor;

@RequiredArgsConstructor
public enum Domain {
    DEVELOP("개발"),
    FASHION("패션");

    private final String name;
}
