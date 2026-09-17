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
import java.time.OffsetDateTime;
import java.util.List;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "trend_analyses", uniqueConstraints = @UniqueConstraint(
        name = "uk_trend_analyses_trend_period", columnNames = {"trend_id", "period"}))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendAnalysis {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(nullable = false, columnDefinition = "metric_period")
    private AnalysisPeriod period;

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Enumerated(EnumType.STRING)
    @Column(name = "trend_types", nullable = false)
    private TrendType[] trendTypes;

    @Column(nullable = false, length = 255)
    private String description;

    @Column(columnDefinition = "text")
    private String summary;

    @Column(columnDefinition = "text")
    private String reason;

    @Column(name = "input_fingerprint", length = 64)
    private String inputFingerprint;

    @Column(name = "analyzed_at", nullable = false)
    private OffsetDateTime analyzedAt;

    public TrendAnalysis(Trend trend, AnalysisPeriod period, List<TrendType> trendTypes,
            String description, String summary, String reason, String inputFingerprint,
            OffsetDateTime analyzedAt) {
        this.trend = trend;
        this.period = period;
        this.trendTypes = trendTypes.toArray(TrendType[]::new);
        this.description = description;
        this.summary = summary;
        this.reason = reason;
        this.inputFingerprint = inputFingerprint;
        this.analyzedAt = analyzedAt;
    }
}
