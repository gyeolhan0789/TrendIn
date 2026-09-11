package com.forever102.member.dto;

import com.forever102.member.domain.Domain;
import java.util.Arrays;
import java.util.List;

public record DomainResponse(
        Domain domain,
        String name
) {

    public static DomainResponse from(Domain domain) {
        return new DomainResponse(domain, domain.getName());
    }

    /**
     * 서비스가 제공하는 분야를 enum 선언 순서대로 반환한다.
     * 분야는 DB가 아니라 enum으로 관리하므로 목록이 바뀌려면 배포가 필요하다.
     */
    public static List<DomainResponse> all() {
        return Arrays.stream(Domain.values())
                .map(DomainResponse::from)
                .toList();
    }
}
