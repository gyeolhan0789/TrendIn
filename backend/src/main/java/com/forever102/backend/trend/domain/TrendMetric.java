package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embedded;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "trend_metrics", indexes = @Index(
        name = "idx_trend_metrics_latest",
        columnList = "trend_id, period, recent_start, recent_end, analyzed_at, id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendMetric {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Column(nullable = false, length = 20)
    private String period;

    @Column(name = "trend_type", nullable = false)
    private String trendType;

    @Column(name = "mention_count", nullable = false)
    private long mentionCount;

    @Column(name = "previous_mention_count", nullable = false)
    private long previousMentionCount;

    @Embedded
    private AnalysisWindow analysisWindow;

    @Column(name = "analyzed_at", nullable = false)
    private OffsetDateTime analyzedAt;

    @Embedded
    private TrendEvidence evidence;

    @Builder
    public TrendMetric(Trend trend, AnalysisPeriod period, String trendType,
            long mentionCount, long previousMentionCount,
            AnalysisWindow analysisWindow, OffsetDateTime analyzedAt,
            TrendEvidence evidence) {
        if (mentionCount < 0 || previousMentionCount < 0) {
            throw new IllegalArgumentException("언급량은 0 이상이어야 합니다.");
        }
        if (trendType == null || trendType.isBlank()) {
            throw new IllegalArgumentException("트렌드 유형은 비어 있을 수 없습니다.");
        }
        this.trend = Objects.requireNonNull(trend);
        this.period = Objects.requireNonNull(period).getValue();
        this.trendType = trendType;
        this.mentionCount = mentionCount;
        this.previousMentionCount = previousMentionCount;
        this.analysisWindow = Objects.requireNonNull(analysisWindow);
        this.analyzedAt = Objects.requireNonNull(analyzedAt);
        this.evidence = evidence;
    }

    public long getGrowthAmount() {
        return mentionCount - previousMentionCount;
    }

    public BigDecimal getGrowthRate() {
        if (previousMentionCount == 0) {
            return null;
        }
        return BigDecimal.valueOf(getGrowthAmount()).multiply(BigDecimal.valueOf(100))
                .divide(BigDecimal.valueOf(previousMentionCount), 1, RoundingMode.HALF_UP);
    }
}
