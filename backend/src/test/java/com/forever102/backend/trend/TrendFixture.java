package com.forever102.backend.trend;

import com.forever102.backend.member.domain.Domain;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.AnalysisWindow;
import com.forever102.backend.trend.domain.Keyword;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendAiAnalysis;
import com.forever102.backend.trend.domain.TrendMetric;
import com.forever102.backend.trend.domain.TrendEvidence;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.test.util.ReflectionTestUtils;

public final class TrendFixture {

    public static final OffsetDateTime END = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");

    private TrendFixture() {
    }

    public static Trend trend() {
        Keyword keyword = new Keyword("Ballet Sneakers", Domain.FASHION);
        ReflectionTestUtils.setField(keyword, "id", 81L);
        Trend trend = new Trend(keyword, "발레 슈즈 디자인을 접목한 스니커즈가 주목받고 있습니다.", END.minusDays(4));
        ReflectionTestUtils.setField(trend, "id", 101L);
        return trend;
    }

    public static TrendMetric metric(Trend trend, AnalysisPeriod period, long current, long previous) {
        return TrendMetric.builder().trend(trend).period(period).trendType("RISING")
                .mentionCount(current).previousMentionCount(previous)
                .analysisWindow(window(period)).analyzedAt(END.plusHours(8))
                .evidence(new TrendEvidence("example-v1", "요청 기간 언급량과 증가율 규칙",
                        Map.of("minimumMentionCount", BigDecimal.valueOf(100),
                                "minimumGrowthRate", BigDecimal.valueOf(100)), "COMPLETE"))
                .build();
    }

    public static TrendAiAnalysis aiAnalysis(Trend trend) {
        return new TrendAiAnalysis(trend, "COMPLETED",
                "관련 콘텐츠에서 발레 스타일 스니커즈 언급이 증가했습니다.",
                "기사들은 신제품 출시를 주요 배경으로 언급합니다.",
                List.of(301L, 302L), END.plusHours(8).plusMinutes(10));
    }

    public static AnalysisWindow window(AnalysisPeriod period) {
        long days = period.getDuration().toDays();
        return new AnalysisWindow(period, END.minusDays(days), END,
                END.minusDays(days * 2), END.minusDays(days));
    }
}
