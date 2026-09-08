package com.forever102.trend.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.data.domain.Page;

public record TrendListResponse(
        List<TrendItemResponse> content,
        int page,
        int size,
        boolean hasNext,
        AnalysisWindowResponse analysisWindow
) {
    public static TrendListResponse from(
            Page<KeywordMetric> metrics, Map<Long, Trend> trendsByKeywordId, AnalysisWindow window) {
        return new TrendListResponse(metrics.getContent().stream()
                .map(metric -> TrendItemResponse.from(
                        trendsByKeywordId.get(metric.getKeyword().getId()), metric))
                .toList(), metrics.getNumber(), metrics.getSize(), metrics.hasNext(),
                AnalysisWindowResponse.from(window));
    }

    public record TrendItemResponse(
            Long trendId,
            Long keywordId,
            String keyword,
            String description,
            DomainResponse domain,
            List<TrendType> trendTypes,
            Integer rank,
            long mentionCount,
            long previousMentionCount,
            long growthAmount,
            BigDecimal growthRate
    ) {
        private static TrendItemResponse from(Trend trend, KeywordMetric metric) {
            return new TrendItemResponse(trend.getId(), trend.getKeyword().getId(),
                    trend.getKeyword().getName(), trend.getDescription(),
                    DomainResponse.from(trend.getKeyword().getDomain()), trend.getTrendTypes(),
                    metric.getMentionRank(), metric.getMentionCount(), metric.getPreviousMentionCount(),
                    metric.getGrowthAmount(), metric.getGrowthRate());
        }
    }

    public record DomainResponse(Domain domain, String name) {
        private static DomainResponse from(Domain domain) {
            return new DomainResponse(domain, domain.getName());
        }
    }

    public record AnalysisWindowResponse(
            OffsetDateTime recentStart,
            OffsetDateTime recentEnd,
            OffsetDateTime previousStart,
            OffsetDateTime previousEnd
    ) {
        private static AnalysisWindowResponse from(AnalysisWindow window) {
            return new AnalysisWindowResponse(window.getRecentStart(), window.getRecentEnd(),
                    window.getPreviousStart(), window.getPreviousEnd());
        }
    }
}
