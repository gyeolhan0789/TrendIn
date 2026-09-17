package com.forever102.trend;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendAnalysis;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.test.util.ReflectionTestUtils;

public final class TrendFixture {

    public static final OffsetDateTime END = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");

    private TrendFixture() {
    }

    public static Trend trend() {
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        ReflectionTestUtils.setField(keyword, "id", 81L);
        Trend trend = new Trend(keyword, END.plusHours(8));
        ReflectionTestUtils.setField(trend, "id", 101L);
        return trend;
    }

    public static TrendAnalysis analysis(Trend trend, AnalysisPeriod period) {
        return new TrendAnalysis(trend, period, List.of(TrendType.RISING),
                "발레 슈즈 디자인을 접목한 스니커즈가 주목받고 있습니다.",
                "관련 콘텐츠에서 발레 스타일 스니커즈 언급이 증가했습니다.",
                "기사들은 신제품 출시를 주요 배경으로 언급합니다.", null, END.plusHours(8));
    }

    public static KeywordMetric metric(Trend trend, AnalysisPeriod period, long current, long previous) {
        return KeywordMetric.builder().keyword(trend.getKeyword()).period(period)
                .periodStart(END.minus(period.getDuration())).periodEnd(END)
                .mentionCount(current).previousMentionCount(previous)
                .growthAmount(current - previous)
                .growthRate(previous == 0 ? null : BigDecimal.valueOf(current - previous)
                        .multiply(BigDecimal.valueOf(100))
                        .divide(BigDecimal.valueOf(previous), 1, java.math.RoundingMode.HALF_UP))
                .mentionRank(1).trendTypes(List.of(TrendType.RISING)).build();
    }

    public static AnalysisWindow window(AnalysisPeriod period) {
        long days = period.getDuration().toDays();
        return new AnalysisWindow(period, END.minusDays(days), END,
                END.minusDays(days * 2), END.minusDays(days));
    }
}
