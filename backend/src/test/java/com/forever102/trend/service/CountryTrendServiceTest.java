package com.forever102.trend.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Domain;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.Keyword;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository.CountryMentionTotal;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository.KeywordMentionTotal;
import com.forever102.trend.repository.KeywordRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import org.assertj.core.groups.Tuple;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Pageable;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class CountryTrendServiceTest {

    @Mock KeywordCountryDailyMetricRepository countryMetricRepository;
    @Mock KeywordRepository keywordRepository;
    @Mock TrendRepository trendRepository;
    CountryTrendService service;

    @BeforeEach
    void setUp() {
        Clock clock = Clock.fixed(Instant.parse("2026-08-31T12:34:56Z"), AnalysisWindow.ANALYSIS_ZONE);
        service = new CountryTrendService(countryMetricRepository, keywordRepository, trendRepository, clock);
    }

    @Test
    @DisplayName("분야의 나라별 언급량을 순위와 함께 돌려주고 전체 합을 함께 싣는다")
    void returnsRankedCountries() {
        LocalDate start = LocalDate.of(2026, 8, 24);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(countryMetricRepository.findCountryTotals(Domain.FASHION, start, end))
                .willReturn(List.of(total("KR", 30), total("US", 30), total("JP", 12)));

        var response = service.getCountries(Domain.FASHION, AnalysisPeriod.DAYS_7);

        assertThat(response.period()).isEqualTo("7D");
        assertThat(response.startDate()).isEqualTo(start);
        assertThat(response.endDate()).isEqualTo(end);
        assertThat(response.totalMentionCount()).isEqualTo(72L);
        // 언급량이 같으면 같은 등수를 받고, 다음 나라는 그만큼 밀립니다.
        assertThat(response.countries()).extracting("rank", "countryCode", "countryName", "mentionCount")
                .containsExactly(
                        Tuple.tuple(1, "KR", "대한민국", 30L),
                        Tuple.tuple(1, "US", "미국", 30L),
                        Tuple.tuple(3, "JP", "일본", 12L));
    }

    @Test
    @DisplayName("나라 하나의 TOP 트렌드를 언급량 순서로 돌려준다")
    void returnsCountryTrends() {
        LocalDate start = LocalDate.of(2026, 8, 24);
        LocalDate end = LocalDate.of(2026, 8, 31);
        var trend = TrendFixture.trend();
        Keyword other = new Keyword("Cargo Pants", Domain.FASHION);
        ReflectionTestUtils.setField(other, "id", 82L);
        given(countryMetricRepository.findKeywordTotalsInCountry(
                any(Domain.class), any(String.class), any(LocalDate.class), any(LocalDate.class),
                any(Pageable.class))).willReturn(List.of(keywordTotal(81L, 40), keywordTotal(82L, 25)));
        given(keywordRepository.findAllById(List.of(81L, 82L)))
                .willReturn(List.of(trend.getKeyword(), other));
        given(trendRepository.findByKeywordIdIn(List.of(81L, 82L))).willReturn(List.of(trend));
        given(countryMetricRepository.sumMentionsInCountry(Domain.FASHION, "KR", start, end))
                .willReturn(100L);

        var response = service.getCountryTrends(Domain.FASHION, "kr", AnalysisPeriod.DAYS_7, 5);

        assertThat(response.countryCode()).isEqualTo("KR");
        assertThat(response.countryName()).isEqualTo("대한민국");
        // 잘라 낸 두 줄의 합(65)이 아니라 나라 전체 합이라야 몫이 제대로 나옵니다.
        assertThat(response.totalMentionCount()).isEqualTo(100L);
        // 트렌드로 묶이지 않은 키워드는 trendId 없이 이름과 언급량만 나갑니다.
        assertThat(response.trends()).extracting("rank", "trendId", "keyword", "mentionCount")
                .containsExactly(
                        Tuple.tuple(1, 101L, "Ballet Sneakers", 40L),
                        Tuple.tuple(2, null, "Cargo Pants", 25L));
    }

    @Test
    @DisplayName("나라 코드가 두 자리 알파벳이 아니면 조회하지 않고 거절한다")
    void rejectsMalformedCountryCode() {
        assertThatThrownBy(() -> service.getCountryTrends(Domain.FASHION, "KOR", AnalysisPeriod.DAYS_7, 5))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.getErrorCode())
                                .isEqualTo(ErrorCode.VALIDATION_ERROR));
        then(countryMetricRepository).shouldHaveNoInteractions();
        then(keywordRepository).shouldHaveNoInteractions();
    }

    private static CountryMentionTotal total(String countryCode, long mentionCount) {
        return new CountryMentionTotal() {
            @Override
            public String getCountryCode() {
                return countryCode;
            }

            @Override
            public long getMentionCount() {
                return mentionCount;
            }
        };
    }

    private static KeywordMentionTotal keywordTotal(long keywordId, long mentionCount) {
        return new KeywordMentionTotal() {
            @Override
            public Long getKeywordId() {
                return keywordId;
            }

            @Override
            public long getMentionCount() {
                return mentionCount;
            }
        };
    }
}
