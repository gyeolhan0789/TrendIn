package com.forever102.trend.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import org.springframework.data.domain.Page;

public record KeywordSearchResponse(
        List<KeywordSearchItemResponse> content,
        int page,
        int size,
        boolean hasNext
) {
    public static KeywordSearchResponse from(
            Page<Keyword> keywords,
            Map<Long, Trend> trendsByKeywordId,
            Map<Long, KeywordMetric> metricsByKeywordId
    ) {
        return new KeywordSearchResponse(keywords.getContent().stream()
                .map(keyword -> KeywordSearchItemResponse.from(keyword,
                        trendsByKeywordId.get(keyword.getId()),
                        metricsByKeywordId.get(keyword.getId())))
                .toList(), keywords.getNumber(), keywords.getSize(), keywords.hasNext());
    }

    public record KeywordSearchItemResponse(
            Long keywordId,
            String keyword,
            DomainResponse domain,
            Long trendId,
            List<TrendType> trendTypes,
            BigDecimal growthRate
    ) {
        private static KeywordSearchItemResponse from(
                Keyword keyword, Trend trend, KeywordMetric metric) {
            if (trend == null) {
                return new KeywordSearchItemResponse(keyword.getId(), keyword.getName(),
                        DomainResponse.from(keyword.getDomain()), null, List.of(), null);
            }
            return new KeywordSearchItemResponse(keyword.getId(), keyword.getName(),
                    DomainResponse.from(keyword.getDomain()), trend.getId(), trend.getTrendTypes(),
                    metric == null ? null : metric.getGrowthRate());
        }
    }

    public record DomainResponse(Domain code, String name) {
        private static DomainResponse from(Domain domain) {
            return new DomainResponse(domain, domain.getName());
        }
    }
}
