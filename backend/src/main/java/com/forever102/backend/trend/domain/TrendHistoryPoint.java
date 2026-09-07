package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
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
@Table(name = "trend_history_points",
        uniqueConstraints = @UniqueConstraint(name = "uk_trend_history_bucket",
                columnNames = {"trend_id", "bucket_unit", "bucket_start"}),
        indexes = @Index(name = "idx_trend_history_lookup",
                columnList = "trend_id, bucket_unit, bucket_start"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TrendHistoryPoint {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "trend_id", nullable = false)
    private Trend trend;

    @Enumerated(EnumType.STRING)
    @Column(name = "bucket_unit", nullable = false, length = 10)
    private HistoryBucketUnit bucketUnit;

    @Column(name = "bucket_start", nullable = false)
    private OffsetDateTime bucketStart;

    @Column(name = "mention_count", nullable = false)
    private long mentionCount;

    public TrendHistoryPoint(Trend trend, HistoryBucketUnit bucketUnit,
            OffsetDateTime bucketStart, long mentionCount) {
        if (mentionCount < 0) {
            throw new IllegalArgumentException("언급량은 0 이상이어야 합니다.");
        }
        this.trend = Objects.requireNonNull(trend);
        this.bucketUnit = Objects.requireNonNull(bucketUnit);
        this.bucketStart = Objects.requireNonNull(bucketStart);
        validateAlignedBucket(bucketStart, bucketUnit);
        this.mentionCount = mentionCount;
    }

    private static void validateAlignedBucket(OffsetDateTime bucketStart, HistoryBucketUnit bucketUnit) {
        var seoul = bucketStart.atZoneSameInstant(AnalysisWindow.ANALYSIS_ZONE);
        boolean minuteAligned = seoul.getMinute() == 0 && seoul.getSecond() == 0 && seoul.getNano() == 0;
        if (!minuteAligned || (bucketUnit == HistoryBucketUnit.DAY && seoul.getHour() != 0)) {
            throw new IllegalArgumentException("버킷 시작 시각이 집계 단위와 맞지 않습니다.");
        }
    }
}
