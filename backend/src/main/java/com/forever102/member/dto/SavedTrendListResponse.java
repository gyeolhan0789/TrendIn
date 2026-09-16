package com.forever102.member.dto;

import com.forever102.member.domain.Domain;
import com.forever102.member.domain.SavedTrend;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.data.domain.Page;

public record SavedTrendListResponse(
        List<SavedTrendResponse> content,
        int page,
        int size,
        boolean hasNext
) {
    public static SavedTrendListResponse from(
            Page<SavedTrend> savedTrends,
            Map<Long, KeywordMetric> metricsByKeywordId
    ) {
        return new SavedTrendListResponse(savedTrends.getContent().stream()
                .map(savedTrend -> SavedTrendResponse.from(savedTrend,
                        metricsByKeywordId.get(savedTrend.getTrend().getKeyword().getId())))
                .toList(), savedTrends.getNumber(), savedTrends.getSize(), savedTrends.hasNext());
    }

    public record SavedTrendResponse(
            Long savedTrendId,
            Long trendId,
            Long keywordId,
            String keyword,
            DomainResponse domain,
            List<TrendType> trendTypes,
            String description,
            Long mentionCount,
            BigDecimal growthRate,
            OffsetDateTime savedAt
    ) {
        private static SavedTrendResponse from(SavedTrend savedTrend, KeywordMetric metric) {
            Trend trend = savedTrend.getTrend();
            return new SavedTrendResponse(savedTrend.getId(), trend.getId(),
                    trend.getKeyword().getId(), trend.getKeyword().getName(),
                    DomainResponse.from(trend.getKeyword().getDomain()),
                    metric == null ? List.of() : metric.getTrendTypes(),
                    trend.getDescription(), metric == null ? null : metric.getMentionCount(),
                    metric == null ? null : metric.getGrowthRate(), savedTrend.getCreatedAt());
        }
    }

    public record DomainResponse(Domain code, String name) {
        private static DomainResponse from(Domain domain) {
            return new DomainResponse(domain, domain.getName());
        }
    }
}
