package com.forever102.member.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.repository.KeywordRelationRepository.RecommendedKeywordProjection;
import java.math.BigDecimal;

public record RecommendedKeywordResponse(
        Long keywordId,
        String keyword,
        DomainResponse domain,
        BigDecimal relationScore
) {
    public static RecommendedKeywordResponse from(RecommendedKeywordProjection projection) {
        return new RecommendedKeywordResponse(
                projection.getKeywordId(),
                projection.getKeyword(),
                DomainResponse.from(projection.getDomain()),
                projection.getRelationScore());
    }

    public record DomainResponse(Domain code, String name) {
        private static DomainResponse from(Domain domain) {
            return new DomainResponse(domain, domain.getName());
        }
    }
}
