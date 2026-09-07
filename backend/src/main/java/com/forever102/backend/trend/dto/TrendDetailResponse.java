package com.forever102.backend.trend.dto;

import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendAiAnalysis;
import com.forever102.backend.trend.domain.TrendMetric;
import com.forever102.backend.trend.domain.TrendEvidence;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

public record TrendDetailResponse(
        Long trendId,
        Long keywordId,
        String keyword,
        String description,
        OffsetDateTime firstDetectedAt,
        DomainResponse domain,
        String trendType,
        Long mentionCount,
        Long previousMentionCount,
        Long growthAmount,
        BigDecimal growthRate,
        AnalysisWindowResponse analysisWindow,
        OffsetDateTime analyzedAt,
        EvidenceResponse evidence,
        AiAnalysisResponse aiAnalysis
) {

    public static TrendDetailResponse from(Trend trend, TrendMetric metric, TrendAiAnalysis aiAnalysis) {
        return new TrendDetailResponse(trend.getId(), trend.getKeyword().getId(),
                trend.getKeyword().getName(), trend.getDescription(), trend.getFirstDetectedAt(),
                DomainResponse.from(trend.getKeyword().getDomain()),
                metric == null ? null : metric.getTrendType(),
                metric == null ? null : metric.getMentionCount(),
                metric == null ? null : metric.getPreviousMentionCount(),
                metric == null ? null : metric.getGrowthAmount(),
                metric == null ? null : metric.getGrowthRate(),
                metric == null ? null : AnalysisWindowResponse.from(metric.getAnalysisWindow()),
                metric == null ? null : metric.getAnalyzedAt(),
                metric == null ? null : EvidenceResponse.from(metric.getEvidence()),
                AiAnalysisResponse.from(aiAnalysis));
    }

    public record DomainResponse(Domain code, String name) {
        private static DomainResponse from(Domain domain) {
            // 기존 Enum의 표시명 접근자가 없으므로 회원 코드를 변경하지 않고 응답에서 매핑한다.
            return new DomainResponse(domain, switch (domain) {
                case DEVELOP -> "개발";
                case FASHION -> "패션";
            });
        }
    }

    public record AnalysisWindowResponse(OffsetDateTime recentStart, OffsetDateTime recentEnd,
            OffsetDateTime previousStart, OffsetDateTime previousEnd) {
        private static AnalysisWindowResponse from(AnalysisWindow window) {
            return new AnalysisWindowResponse(window.getRecentStart(), window.getRecentEnd(),
                    window.getPreviousStart(), window.getPreviousEnd());
        }
    }

    public record EvidenceResponse(String ruleVersion, String ruleDescription,
            Map<String, BigDecimal> appliedThresholds, String dataCoverage) {
        private static EvidenceResponse from(TrendEvidence evidence) {
            return evidence == null ? null : new EvidenceResponse(evidence.getRuleVersion(),
                    evidence.getRuleDescription(), evidence.getAppliedThresholds() == null ? null
                            : Map.copyOf(evidence.getAppliedThresholds()), evidence.getDataCoverage());
        }
    }

    public record AiAnalysisResponse(String status, String summary, String reason,
            List<Long> sourceContentIds, OffsetDateTime generatedAt) {
        private static AiAnalysisResponse from(TrendAiAnalysis analysis) {
            return analysis == null || analysis.getStatus() == null ? null
                    : new AiAnalysisResponse(analysis.getStatus(), analysis.getSummary(),
                            analysis.getReason(), List.copyOf(analysis.getSourceContentIds()),
                            analysis.getGeneratedAt());
        }
    }
}
