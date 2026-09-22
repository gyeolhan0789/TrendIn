package com.forever102.trend.dto;

import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import java.time.LocalDate;
import java.util.List;

/**
 * 분야 하나를 나라별로 갈라 본 언급량입니다. 지도를 칠하는 값이자 국가 목록의 값입니다.
 *
 * 트렌드 하나를 보는 {@link TrendRegionResponse} 와 모양을 맞춰 두었습니다. 같은 화면에서
 * 두 조회를 번갈아 쓰기 때문에, 순위와 언급량을 읽는 방법이 달라지면 화면이 갈라집니다.
 */
public record CountryRegionResponse(
        Domain domain,
        String period,
        String timezone,
        LocalDate startDate,
        LocalDate endDate,
        /** 잘라 내기 전 전체 언급량. 나라별 몫을 내는 분모입니다. */
        long totalMentionCount,
        List<CountryItemResponse> countries
) {
    public static CountryRegionResponse of(Domain domain, AnalysisPeriod period,
            LocalDate startDate, LocalDate endDate, long totalMentionCount,
            List<CountryItemResponse> countries) {
        return new CountryRegionResponse(domain, period.getValue(),
                AnalysisWindow.ANALYSIS_ZONE.getId(), startDate, endDate, totalMentionCount,
                List.copyOf(countries));
    }

    public record CountryItemResponse(
            int rank,
            String countryCode,
            String countryName,
            long mentionCount
    ) {
    }
}
