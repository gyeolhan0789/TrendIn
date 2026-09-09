package com.forever102.trend.domain;

import jakarta.persistence.CheckConstraint;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "keyword_relations")
@IdClass(KeywordRelation.Key.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class KeywordRelation {

    @Id
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "source_keyword_id", nullable = false)
    private Keyword sourceKeyword;

    @Id
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "target_keyword_id", nullable = false)
    private Keyword targetKeyword;

    @Column(name = "relation_score", nullable = false, precision = 5, scale = 2,
            check = @CheckConstraint(constraint = "relation_score between 0 and 100"))
    private BigDecimal relationScore;

    @Column(name = "co_occurrence_count", nullable = false)
    private long coOccurrenceCount;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    public KeywordRelation(Keyword sourceKeyword, Keyword targetKeyword, BigDecimal relationScore,
            long coOccurrenceCount, OffsetDateTime updatedAt) {
        this.sourceKeyword = Objects.requireNonNull(sourceKeyword);
        this.targetKeyword = Objects.requireNonNull(targetKeyword);
        this.relationScore = Objects.requireNonNull(relationScore);
        if (relationScore.compareTo(BigDecimal.ZERO) < 0
                || relationScore.compareTo(BigDecimal.valueOf(100)) > 0) {
            throw new IllegalArgumentException("연관도 점수는 0 이상 100 이하여야 합니다.");
        }
        this.coOccurrenceCount = coOccurrenceCount;
        this.updatedAt = Objects.requireNonNull(updatedAt);
    }

    @NoArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private Long sourceKeyword;
        private Long targetKeyword;
    }
}
