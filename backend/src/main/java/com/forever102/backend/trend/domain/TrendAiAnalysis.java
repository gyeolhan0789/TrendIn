package com.forever102.backend.trend.domain;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OrderColumn;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "trend_ai_analyses", indexes = @Index(
        name = "idx_trend_ai_analyses_latest", columnList = "trend_id, generated_at, id"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendAiAnalysis {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Column(nullable = false)
    private String status;

    @Column(columnDefinition = "text")
    private String summary;

    @Column(columnDefinition = "text")
    private String reason;

    @Column(name = "generated_at", nullable = false)
    private OffsetDateTime generatedAt;

    @ElementCollection
    @CollectionTable(name = "trend_ai_analysis_sources", joinColumns = @JoinColumn(name = "ai_analysis_id"))
    @Column(name = "content_id", nullable = false)
    @OrderColumn(name = "source_order")
    private List<Long> sourceContentIds = new ArrayList<>();

    public TrendAiAnalysis(Trend trend, String status, String summary, String reason,
            List<Long> sourceContentIds, OffsetDateTime generatedAt) {
        this.trend = Objects.requireNonNull(trend);
        this.status = Objects.requireNonNull(status);
        this.summary = summary;
        this.reason = reason;
        this.sourceContentIds = new ArrayList<>(List.copyOf(sourceContentIds));
        this.generatedAt = Objects.requireNonNull(generatedAt);
    }
}
