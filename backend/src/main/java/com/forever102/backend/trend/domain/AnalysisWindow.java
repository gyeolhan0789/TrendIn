package com.forever102.backend.trend.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import java.time.Clock;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Embeddable
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AnalysisWindow {

    public static final ZoneId ANALYSIS_ZONE = ZoneId.of("Asia/Seoul");

    @Column(name = "recent_start", nullable = false)
    private OffsetDateTime recentStart;

    @Column(name = "recent_end", nullable = false)
    private OffsetDateTime recentEnd;

    @Column(name = "previous_start", nullable = false)
    private OffsetDateTime previousStart;

    @Column(name = "previous_end", nullable = false)
    private OffsetDateTime previousEnd;

    public AnalysisWindow(AnalysisPeriod period, OffsetDateTime recentStart, OffsetDateTime recentEnd,
            OffsetDateTime previousStart, OffsetDateTime previousEnd) {
        if (recentStart == null || recentEnd == null || previousStart == null || previousEnd == null
                || period == null
                || !java.time.Duration.between(recentStart, recentEnd).equals(period.getDuration())
                || !java.time.Duration.between(previousStart, previousEnd).equals(period.getDuration())
                || !previousEnd.isEqual(recentStart)
                || !isSeoulDayBoundary(recentStart) || !isSeoulDayBoundary(recentEnd)
                || !isSeoulDayBoundary(previousStart) || !isSeoulDayBoundary(previousEnd)) {
            throw new IllegalArgumentException("분석 구간은 Asia/Seoul 기준으로 연속된 요청 기간이어야 합니다.");
        }
        this.recentStart = recentStart;
        this.recentEnd = recentEnd;
        this.previousStart = previousStart;
        this.previousEnd = previousEnd;
    }

    public static AnalysisWindow completed(AnalysisPeriod period, Clock clock) {
        OffsetDateTime recentEnd = clock.instant().atZone(ANALYSIS_ZONE).toLocalDate()
                .atStartOfDay(ANALYSIS_ZONE).toOffsetDateTime();
        OffsetDateTime recentStart = recentEnd.minus(period.getDuration());
        return new AnalysisWindow(period, recentStart, recentEnd,
                recentStart.minus(period.getDuration()), recentStart);
    }

    private static boolean isSeoulDayBoundary(OffsetDateTime dateTime) {
        return dateTime.toZonedDateTime().withZoneSameInstant(ANALYSIS_ZONE).toLocalTime()
                .equals(java.time.LocalTime.MIDNIGHT);
    }
}
