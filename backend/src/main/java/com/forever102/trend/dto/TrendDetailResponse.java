package com.forever102.trend.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

public record TrendDetailResponse(
        Long trendId,
        Long keywordId,
        String keyword,
        String description,
        DomainResponse domain,
        List<TrendType> trendTypes,
        Long mentionCount,
        Long previousMentionCount,
        Long growthAmount,
        BigDecimal growthRate,
        AnalysisWindowResponse analysisWindow,
        String summary,
        String reason
) {

    public static TrendDetailResponse from(Trend trend, KeywordMetric metric, AnalysisPeriod period) {
        return new TrendDetailResponse(
                trend.getId(), trend.getKeyword().getId(), trend.getKeyword().getName(),
                trend.getDescription(), DomainResponse.from(trend.getKeyword().getDomain()),
                trend.getTrendTypes(), metric == null ? null : metric.getMentionCount(),
                metric == null ? null : metric.getPreviousMentionCount(),
                metric == null ? null : metric.getGrowthAmount(),
                metric == null ? null : metric.getGrowthRate(),
                metric == null ? null : AnalysisWindowResponse.from(metric, period),
                trend.getSummary(), trend.getReason());
    }

    public record DomainResponse(Domain code, String name) {
        private static DomainResponse from(Domain domain) {
            return new DomainResponse(domain, domain.getName());
        }
    }

    public record AnalysisWindowResponse(OffsetDateTime recentStart, OffsetDateTime recentEnd,
            OffsetDateTime previousStart, OffsetDateTime previousEnd) {
        private static AnalysisWindowResponse from(KeywordMetric metric, AnalysisPeriod period) {
            return new AnalysisWindowResponse(metric.getPeriodStart(), metric.getPeriodEnd(),
                    metric.getPeriodStart().minus(period.getDuration()), metric.getPeriodStart());
        }
    }
}
