package com.forever102.trend.domain;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import jakarta.persistence.EnumeratedValue;
import java.time.Duration;
import java.util.Arrays;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum AnalysisPeriod {
    HOURS_24("24H", Duration.ofDays(1)),
    DAYS_7("7D", Duration.ofDays(7)),
    DAYS_30("30D", Duration.ofDays(30));

    @EnumeratedValue
    private final String value;
    private final Duration duration;

    public Duration getHistoryBucketDuration() {
        return switch (this) {
            case HOURS_24 -> Duration.ofHours(1);
            case DAYS_7 -> Duration.ofDays(1);
            case DAYS_30 -> Duration.ofDays(3);
        };
    }

    public static AnalysisPeriod from(String value) {
        return Arrays.stream(values())
                .filter(period -> period.value.equals(value))
                .findFirst()
                .orElseThrow(() -> new BusinessException(ErrorCode.VALIDATION_ERROR));
    }
}
