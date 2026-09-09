package com.forever102.trend.dto;

import com.forever102.trend.domain.KeywordRelation;
import java.math.BigDecimal;
import java.util.List;

public record TrendRelatedKeywordResponse(
        Long trendId,
        List<RelatedKeywordResponse> relatedKeywords
) {
    public static TrendRelatedKeywordResponse from(
            Long trendId, List<KeywordRelation> relations) {
        return new TrendRelatedKeywordResponse(trendId, relations.stream()
                .map(RelatedKeywordResponse::from)
                .toList());
    }

    public record RelatedKeywordResponse(
            Long keywordId,
            String keyword,
            BigDecimal relationScore
    ) {
        private static RelatedKeywordResponse from(KeywordRelation relation) {
            return new RelatedKeywordResponse(relation.getTargetKeyword().getId(),
                    relation.getTargetKeyword().getName(), relation.getRelationScore());
        }
    }
}
