package com.forever102.backend.trend.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.TrendFixture;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.ValueSource;

class TrendMetricTest {

    @ParameterizedTest
    @CsvSource({"24H,HOURS_24", "7D,DAYS_7", "30D,DAYS_30"})
    @DisplayName("허용된 API 기간 값을 지표 기간으로 변환한다")
    void parsesPeriod(String value, AnalysisPeriod expected) {
        assertThat(AnalysisPeriod.from(value)).isEqualTo(expected);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "24h", "1D", "7", "30d"})
    @DisplayName("허용되지 않은 기간 값은 400 비즈니스 예외이다")
    void rejectsInvalidPeriod(String value) {
        assertThatThrownBy(() -> AnalysisPeriod.from(value))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.VALIDATION_ERROR));
    }

    @ParameterizedTest
    @EnumSource(AnalysisPeriod.class)
    @DisplayName("Asia/Seoul 자정 기준으로 연속된 요청 기간 구간을 허용한다")
    void acceptsPeriodWindow(AnalysisPeriod period) {
        assertThat(TrendFixture.window(period).getRecentEnd()).isEqualTo(TrendFixture.END);
    }

    @ParameterizedTest
    @EnumSource(AnalysisPeriod.class)
    @DisplayName("현재 시각에서 Asia/Seoul 기준 완료된 공통 분석 구간을 계산한다")
    void calculatesCompletedWindow(AnalysisPeriod period) {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), ZoneId.of("UTC"));

        AnalysisWindow window = AnalysisWindow.completed(period, clock);

        assertThat(window.getRecentEnd()).isEqualTo(TrendFixture.END);
        assertThat(window.getRecentStart()).isEqualTo(TrendFixture.END.minus(period.getDuration()));
        assertThat(window.getPreviousEnd()).isEqualTo(window.getRecentStart());
        assertThat(window.getPreviousStart()).isEqualTo(window.getRecentStart().minus(period.getDuration()));
    }

    @Test
    @DisplayName("요청 기간과 길이가 다른 분석 구간을 거부한다")
    void rejectsWrongWindowLength() {
        var end = TrendFixture.END;
        assertThatThrownBy(() -> new AnalysisWindow(AnalysisPeriod.DAYS_7,
                end.minusDays(1), end, end.minusDays(2), end.minusDays(1)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    @DisplayName("Asia/Seoul 자정 경계가 아닌 분석 구간을 거부한다")
    void rejectsNonSeoulBoundary() {
        OffsetDateTime end = TrendFixture.END.plusHours(1);
        assertThatThrownBy(() -> new AnalysisWindow(AnalysisPeriod.HOURS_24,
                end.minusDays(1), end, end.minusDays(2), end.minusDays(1)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @ParameterizedTest
    @CsvSource({"430,123,307,249.6", "50,100,-50,-50.0", "100,100,0,0.0"})
    @DisplayName("증가량과 소수 첫째 자리 증가율을 계산한다")
    void calculatesGrowth(long current, long previous, long amount, BigDecimal rate) {
        var metric = TrendFixture.metric(TrendFixture.trend(), AnalysisPeriod.DAYS_7, current, previous);
        assertThat(metric.getGrowthAmount()).isEqualTo(amount);
        assertThat(metric.getGrowthRate()).isEqualByComparingTo(rate);
    }

    @Test
    @DisplayName("이전 언급량이 0이면 증가율은 null이다")
    void returnsNullForZeroBaseline() {
        var metric = TrendFixture.metric(TrendFixture.trend(), AnalysisPeriod.DAYS_30, 430, 0);
        assertThat(metric.getGrowthRate()).isNull();
    }
}
