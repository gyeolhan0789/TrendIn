package com.forever102.backend.trend.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.forever102.backend.trend.TrendFixture;
import java.math.BigDecimal;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class TrendAnalysisTest {

    @ParameterizedTest
    @CsvSource({"430,123,307,249.6", "50,100,-50,-50.0", "0,100,-100,-100.0", "100,100,0,0.0"})
    @DisplayName("언급량 차이와 소수 첫째 자리 증가율을 계산한다")
    void calculatesGrowth(long current, long previous, long amount, BigDecimal rate) {
        // given
        TrendAnalysis analysis = TrendFixture.analysis(TrendFixture.trend(), current, previous);
        // when & then
        assertThat(analysis.getGrowthAmount()).isEqualTo(amount);
        assertThat(analysis.getGrowthRate()).isEqualByComparingTo(rate);
    }

    @ParameterizedTest
    @CsvSource({"0", "430"})
    @DisplayName("이전 언급량이 0이면 증가율은 null이다")
    void returnsNullForZeroBaseline(long current) {
        // given
        TrendAnalysis analysis = TrendFixture.analysis(TrendFixture.trend(), current, 0);
        // when & then
        assertThat(analysis.getGrowthRate()).isNull();
        assertThat(analysis.getGrowthAmount()).isEqualTo(current);
    }

    @Test
    @DisplayName("24H가 아닌 분석 구간을 저장하지 않는다")
    void rejectsWeeklyWindow() {
        // given
        var end = TrendFixture.END;
        // when & then
        assertThatThrownBy(() -> new AnalysisWindow(end.minusDays(7), end, end.minusDays(14), end.minusDays(7)))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    @DisplayName("서로 이어지지 않는 비교 구간을 저장하지 않는다")
    void rejectsGapBetweenWindows() {
        // given
        var end = TrendFixture.END;
        // when & then
        assertThatThrownBy(() -> new AnalysisWindow(end.minusDays(1), end, end.minusDays(3), end.minusDays(2)))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
