package com.forever102.backend.trend.domain;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
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

    private final String value;
    private final Duration duration;

    public HistoryBucketUnit getHistoryBucketUnit() {
        return this == HOURS_24 ? HistoryBucketUnit.HOUR : HistoryBucketUnit.DAY;
    }

    public static AnalysisPeriod from(String value) {
        return Arrays.stream(values())
                .filter(period -> period.value.equals(value))
                .findFirst()
                .orElseThrow(() -> new BusinessException(ErrorCode.VALIDATION_ERROR));
    }
}
