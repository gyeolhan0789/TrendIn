package com.forever102.backend.trend.domain;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Embeddable;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OrderColumn;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Embeddable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendAiAnalysis {

    @Column(name = "ai_status")
    private String status;

    @Column(name = "ai_summary", columnDefinition = "text")
    private String summary;

    @Column(name = "ai_reason", columnDefinition = "text")
    private String reason;

    @Column(name = "ai_generated_at")
    private OffsetDateTime generatedAt;

    @ElementCollection
    @CollectionTable(name = "trend_analysis_sources", joinColumns = @JoinColumn(name = "analysis_id"))
    @Column(name = "content_id", nullable = false)
    @OrderColumn(name = "source_order")
    private List<Long> sourceContentIds = new ArrayList<>();

    public TrendAiAnalysis(String status, String summary, String reason,
            List<Long> sourceContentIds, OffsetDateTime generatedAt) {
        this.status = Objects.requireNonNull(status);
        this.summary = summary;
        this.reason = reason;
        this.sourceContentIds = new ArrayList<>(List.copyOf(sourceContentIds));
        this.generatedAt = generatedAt;
    }
}
