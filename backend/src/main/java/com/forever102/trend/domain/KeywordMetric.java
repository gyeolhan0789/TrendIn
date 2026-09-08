package com.forever102.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "keyword_metrics", uniqueConstraints = @UniqueConstraint(
        name = "uk_keyword_metrics_period",
        columnNames = {"keyword_id", "period", "period_start", "period_end"}))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class KeywordMetric {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false, columnDefinition = "metric_period")
    private AnalysisPeriod period;

    @Column(name = "period_start", nullable = false)
    private OffsetDateTime periodStart;

    @Column(name = "period_end", nullable = false)
    private OffsetDateTime periodEnd;

    @Column(name = "mention_count", nullable = false)
    private long mentionCount;

    @Column(name = "previous_mention_count", nullable = false)
    private long previousMentionCount;

    @Column(name = "growth_amount", nullable = false)
    private long growthAmount;

    @Column(name = "growth_rate")
    private BigDecimal growthRate;

    @Column(name = "mention_rank")
    private Integer mentionRank;

    @Builder
    public KeywordMetric(Keyword keyword, AnalysisPeriod period,
            OffsetDateTime periodStart, OffsetDateTime periodEnd,
            long mentionCount, long previousMentionCount, long growthAmount,
            BigDecimal growthRate, Integer mentionRank) {
        if (mentionCount < 0 || previousMentionCount < 0) {
            throw new IllegalArgumentException("언급량은 0 이상이어야 합니다.");
        }
        if (mentionRank != null && mentionRank <= 0) {
            throw new IllegalArgumentException("언급 순위는 양수여야 합니다.");
        }
        if (periodStart == null || periodEnd == null || !periodEnd.isAfter(periodStart)) {
            throw new IllegalArgumentException("지표 종료 시각은 시작 시각보다 뒤여야 합니다.");
        }
        this.keyword = Objects.requireNonNull(keyword);
        this.period = Objects.requireNonNull(period);
        this.periodStart = periodStart;
        this.periodEnd = periodEnd;
        this.mentionCount = mentionCount;
        this.previousMentionCount = previousMentionCount;
        this.growthAmount = growthAmount;
        this.growthRate = growthRate;
        this.mentionRank = mentionRank;
    }
}
