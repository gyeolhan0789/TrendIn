package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.time.Duration;
import java.time.OffsetDateTime;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Embeddable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AnalysisWindow {

    @Column(name = "recent_start", nullable = false)
    private OffsetDateTime recentStart;

    @Column(name = "recent_end", nullable = false)
    private OffsetDateTime recentEnd;

    @Column(name = "previous_start", nullable = false)
    private OffsetDateTime previousStart;

    @Column(name = "previous_end", nullable = false)
    private OffsetDateTime previousEnd;

    public AnalysisWindow(OffsetDateTime recentStart, OffsetDateTime recentEnd,
            OffsetDateTime previousStart, OffsetDateTime previousEnd) {
        if (recentStart == null || recentEnd == null || previousStart == null || previousEnd == null
                || !Duration.between(recentStart, recentEnd).equals(Duration.ofHours(24))
                || !Duration.between(previousStart, previousEnd).equals(Duration.ofHours(24))
                || !previousEnd.isEqual(recentStart)) {
            throw new IllegalArgumentException("분석 구간은 연속된 두 24시간 구간이어야 합니다.");
        }
        this.recentStart = recentStart;
        this.recentEnd = recentEnd;
        this.previousStart = previousStart;
        this.previousEnd = previousEnd;
    }
}
