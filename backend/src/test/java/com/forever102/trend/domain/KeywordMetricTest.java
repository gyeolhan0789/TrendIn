package com.forever102.trend.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

class KeywordMetricTest {

    @ParameterizedTest
    @CsvSource({"24H,HOURS_24", "7D,DAYS_7", "30D,DAYS_30"})
    void parsesPeriod(String value, AnalysisPeriod expected) {
        assertThat(AnalysisPeriod.from(value)).isEqualTo(expected);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "24h", "1D", "7", "30d"})
    void rejectsInvalidPeriod(String value) {
        assertThatThrownBy(() -> AnalysisPeriod.from(value))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.VALIDATION_ERROR));
    }

    @ParameterizedTest
    @EnumSource(AnalysisPeriod.class)
    @DisplayName("현재 시각에서 Asia/Seoul 기준 완료 구간을 계산한다")
    void calculatesCompletedWindow(AnalysisPeriod period) {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), ZoneId.of("UTC"));
        AnalysisWindow window = AnalysisWindow.completed(period, clock);
        assertThat(window.getRecentEnd()).isEqualTo(TrendFixture.END);
        assertThat(window.getRecentStart()).isEqualTo(TrendFixture.END.minus(period.getDuration()));
    }

    @Test
    @DisplayName("30D 시계열은 3일 단위 10개 버킷을 사용한다")
    void usesThreeDayBucketsForThirtyDays() {
        assertThat(AnalysisPeriod.DAYS_30.getHistoryBucketDuration()).isEqualTo(java.time.Duration.ofDays(3));
    }
}
