package com.forever102.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.OffsetDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "keyword_metric_history", uniqueConstraints = @UniqueConstraint(
        name = "uk_keyword_metric_history_bucket",
        columnNames = {"keyword_id", "bucket_start", "bucket_end"}))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class KeywordMetricHistory {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "keyword_id", nullable = false)
    private Keyword keyword;

    @Column(name = "bucket_start", nullable = false)
    private OffsetDateTime bucketStart;

    @Column(name = "bucket_end", nullable = false)
    private OffsetDateTime bucketEnd;

    @Column(name = "mention_count", nullable = false)
    private long mentionCount;

    public KeywordMetricHistory(Keyword keyword, OffsetDateTime bucketStart,
            OffsetDateTime bucketEnd, long mentionCount) {
        if (mentionCount < 0) {
            throw new IllegalArgumentException("언급량은 0 이상이어야 합니다.");
        }
        if (bucketStart == null || bucketEnd == null || !bucketEnd.isAfter(bucketStart)) {
            throw new IllegalArgumentException("버킷 종료 시각은 시작 시각보다 뒤여야 합니다.");
        }
        this.keyword = Objects.requireNonNull(keyword);
        this.bucketStart = bucketStart;
        this.bucketEnd = bucketEnd;
        this.mentionCount = mentionCount;
    }
}
