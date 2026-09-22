package com.forever102.trend.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import java.time.LocalDate;
import java.util.List;

/**
 * 나라 하나에서 많이 언급된 트렌드 차례입니다.
 *
 * trendId 는 비어 있을 수 있습니다. 나라별 언급은 키워드 단위로 쌓이는데 아직 트렌드로
 * 묶이지 않은 키워드가 있어서입니다. 그런 줄은 이름과 언급량만 읽히고 상세로 갈 수 없습니다.
 */
public record CountryTrendResponse(
        Domain domain,
        String countryCode,
        String countryName,
        String period,
        String timezone,
        LocalDate startDate,
        LocalDate endDate,
        /** 잘라 내기 전 이 나라의 전체 언급량. 목록을 TOP N 으로 잘라도 몫은 제대로 나옵니다. */
        long totalMentionCount,
        List<CountryTrendItemResponse> trends
) {
    public static CountryTrendResponse of(Domain domain, String countryCode, String countryName,
            AnalysisPeriod period, LocalDate startDate, LocalDate endDate, long totalMentionCount,
            List<CountryTrendItemResponse> trends) {
        return new CountryTrendResponse(domain, countryCode, countryName, period.getValue(),
                AnalysisWindow.ANALYSIS_ZONE.getId(), startDate, endDate, totalMentionCount,
                List.copyOf(trends));
    }

    public record CountryTrendItemResponse(
            int rank,
            Long trendId,
            Long keywordId,
            String keyword,
            long mentionCount
    ) {
    }
}
