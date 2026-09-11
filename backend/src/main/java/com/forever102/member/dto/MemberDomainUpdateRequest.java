package com.forever102.member.dto;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import jakarta.validation.constraints.NotNull;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * 분야 코드를 enum이 아닌 문자열로 받는다.
 * enum으로 바로 받으면 정의되지 않은 값이 역직렬화 단계에서 걸려 400이 나가는데,
 * 명세는 이 경우 404 DOMAIN_NOT_FOUND를 요구하기 때문이다.
 */
public record MemberDomainUpdateRequest(

        @NotNull(message = "관심 분야 목록은 필수입니다.")
        List<String> domains
) {

    /**
     * 요청의 분야 코드를 enum으로 바꾼다. 같은 분야를 여러 번 보내도 하나로 합친다.
     */
    public Set<Domain> toDomains() {
        Set<Domain> converted = new LinkedHashSet<>();
        for (String domain : domains) {
            converted.add(parse(domain));
        }
        return converted;
    }

    private Domain parse(String domain) {
        if (domain == null) {
            throw new BusinessException(ErrorCode.DOMAIN_NOT_FOUND);
        }
        try {
            return Domain.valueOf(domain.strip().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.DOMAIN_NOT_FOUND);
        }
    }
}
