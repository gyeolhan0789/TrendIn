package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.CountryNames;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.CountryRegionResponse;
import com.forever102.trend.dto.CountryRegionResponse.CountryItemResponse;
import com.forever102.trend.dto.CountryTrendResponse;
import com.forever102.trend.dto.CountryTrendResponse.CountryTrendItemResponse;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository.CountryMentionTotal;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository.KeywordMentionTotal;
import com.forever102.trend.repository.KeywordConceptRepository;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 나라를 먼저 고르고 그 나라의 트렌드를 보는 조회입니다.
 *
 * 트렌드 하나를 나라별로 가르는 {@link TrendRegionService} 와 같은 표를 반대로 읽습니다.
 * 그래서 두 조회가 같은 구간을 봐야 화면에서 숫자가 맞습니다. 구간은 양쪽 모두
 * {@link AnalysisWindow#completed} 가 정하는, 이미 끝난 구간입니다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class CountryTrendService {

    /** ISO 3166-1 alpha-2. 저장할 때 거르는 규칙과 같아야 없는 나라를 찾다 빈손으로 돌아오지 않습니다. */
    private static final Pattern COUNTRY_CODE = Pattern.compile("[A-Z]{2}");

    /** 한 나라에서 한 번에 내려 줄 트렌드 수의 윗선. 화면은 다섯 줄을 쓰지만 더 받아 볼 여지는 둡니다. */
    private static final int MAX_TRENDS = 50;

    private final KeywordCountryDailyMetricRepository countryMetricRepository;
    private final KeywordRepository keywordRepository;
    private final KeywordConceptRepository keywordConceptRepository;
    private final TrendRepository trendRepository;
    private final Clock trendClock;

    /** 분야 하나를 나라별로 갈라 언급량이 많은 차례로 돌려줍니다. 지도 전체를 칠하는 값입니다. */
    public CountryRegionResponse getCountries(Domain domain, AnalysisPeriod period) {
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        LocalDate startDate = window.getRecentStart().toLocalDate();
        LocalDate endDate = window.getRecentEnd().toLocalDate();

        List<CountryMentionTotal> totals =
                countryMetricRepository.findCountryTotals(domain, startDate, endDate);
        long totalMentionCount = totals.stream().mapToLong(CountryMentionTotal::getMentionCount).sum();
        return CountryRegionResponse.of(domain, period, startDate, endDate, totalMentionCount,
                rank(totals));
    }

    /** 나라 하나에서 많이 언급된 트렌드를 돌려줍니다. size 는 잘라 낼 줄 수입니다. */
    public CountryTrendResponse getCountryTrends(Domain domain, String countryCode,
            AnalysisPeriod period, int size) {
        String normalizedCode = normalizeCountryCode(countryCode);
        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        LocalDate startDate = window.getRecentStart().toLocalDate();
        LocalDate endDate = window.getRecentEnd().toLocalDate();

        List<KeywordMentionTotal> totals = countryMetricRepository.findKeywordTotalsInCountry(
                domain, normalizedCode, startDate, endDate,
                PageRequest.of(0, Math.min(size, MAX_TRENDS)));
        /*
         * 몫의 분모는 잘라 내기 전 이 나라의 전체 언급량입니다. 내려 준 다섯 줄만 더하면
         * 언제나 100% 가 되어, 이 나라에서 그 트렌드가 얼마나 큰지가 지워집니다.
         */
        long totalMentionCount = countryMetricRepository.sumMentionsInCountry(
                domain, normalizedCode, startDate, endDate);
        return CountryTrendResponse.of(domain, normalizedCode, CountryNames.of(normalizedCode),
                period, startDate, endDate, totalMentionCount, items(domain, totals));
    }

    private List<CountryTrendItemResponse> items(Domain domain, List<KeywordMentionTotal> totals) {
        if (totals.isEmpty()) {
            return List.of();
        }
        List<Long> keywordIds = totals.stream().map(KeywordMentionTotal::getKeywordId).toList();
        Map<Long, Keyword> keywords = keywordRepository.findAllById(keywordIds).stream()
                .collect(Collectors.toMap(Keyword::getId, Function.identity()));
        /* 키워드마다 트렌드가 있다는 보장이 없어, 없으면 trendId 를 비워 둡니다. */
        Map<Long, Trend> trendsByKeywordId = trendRepository.findByKeywordIdIn(keywordIds).stream()
                .collect(Collectors.toMap(trend -> trend.getKeyword().getId(), Function.identity()));
        /*
         * 개념 사전은 패션 어휘로만 채워져 있습니다. 다른 분야 키워드에 대 보면 철자만 같은 패션
         * 개념이 붙으므로 아예 찾지 않습니다.
         */
        Map<Long, String> conceptNames = domain == Domain.FASHION
                ? keywordConceptRepository.findConceptNames(keywordIds)
                : Map.of();

        List<CountryTrendItemResponse> result = new ArrayList<>();
        long previousCount = Long.MIN_VALUE;
        int rank = 0;
        for (int index = 0; index < totals.size(); index++) {
            KeywordMentionTotal total = totals.get(index);
            if (total.getMentionCount() != previousCount) {
                rank = index + 1;
                previousCount = total.getMentionCount();
            }
            Keyword keyword = keywords.get(total.getKeywordId());
            if (keyword == null) {
                continue;
            }
            Trend trend = trendsByKeywordId.get(total.getKeywordId());
            result.add(new CountryTrendItemResponse(rank, trend == null ? null : trend.getId(),
                    keyword.getId(), keyword.getName(), conceptNames.get(keyword.getId()),
                    total.getMentionCount()));
        }
        return List.copyOf(result);
    }

    /** 언급량이 같으면 같은 등수를 줍니다. TrendRegionService 와 같은 규칙입니다. */
    private List<CountryItemResponse> rank(List<CountryMentionTotal> totals) {
        List<CountryItemResponse> result = new ArrayList<>();
        long previousCount = Long.MIN_VALUE;
        int rank = 0;
        for (int index = 0; index < totals.size(); index++) {
            CountryMentionTotal total = totals.get(index);
            if (total.getMentionCount() != previousCount) {
                rank = index + 1;
                previousCount = total.getMentionCount();
            }
            result.add(new CountryItemResponse(rank, total.getCountryCode(),
                    CountryNames.of(total.getCountryCode()), total.getMentionCount()));
        }
        return List.copyOf(result);
    }

    private String normalizeCountryCode(String countryCode) {
        String normalized = countryCode == null ? "" : countryCode.strip().toUpperCase(Locale.ROOT);
        if (!COUNTRY_CODE.matcher(normalized).matches()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        return normalized;
    }
}
