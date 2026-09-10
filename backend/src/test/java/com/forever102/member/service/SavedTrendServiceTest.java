package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;

import com.forever102.member.domain.Member;
import com.forever102.member.domain.SavedTrend;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.repository.SavedTrendRepository;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.KeywordMetricRepository;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SavedTrendServiceTest {

    @Mock SavedTrendRepository savedTrendRepository;
    @Mock KeywordMetricRepository keywordMetricRepository;

    private SavedTrendService service;
    private Clock clock;

    @BeforeEach
    void setUp() {
        clock = Clock.fixed(TrendFixture.END.plusHours(12).toInstant(), ZoneOffset.UTC);
        service = new SavedTrendService(savedTrendRepository, keywordMetricRepository, clock);
    }

    @Test
    @DisplayName("저장한 트렌드에 선택 기간의 언급량과 증가율을 결합한다")
    void returnsSavedTrendsWithSelectedPeriodMetric() {
        // given
        Trend trend = TrendFixture.trend();
        SavedTrend savedTrend = savedTrend(trend, 15L);
        KeywordMetric metric = TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123);
        PageRequest pageable = PageRequest.of(0, 20);
        AnalysisWindow window = AnalysisWindow.completed(AnalysisPeriod.DAYS_7, clock);
        given(savedTrendRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(1L, pageable))
                .willReturn(new PageImpl<>(List.of(savedTrend), pageable, 1));
        given(keywordMetricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                List.of(81L), AnalysisPeriod.DAYS_7,
                window.getRecentStart(), window.getRecentEnd())).willReturn(List.of(metric));

        // when
        SavedTrendListResponse response = service.getSavedTrends(1L, AnalysisPeriod.DAYS_7, 0, 20);

        // then
        assertThat(response.content()).singleElement().satisfies(item -> {
            assertThat(item.savedTrendId()).isEqualTo(15L);
            assertThat(item.mentionCount()).isEqualTo(430L);
            assertThat(item.growthRate()).isEqualByComparingTo("249.6");
        });
    }

    @Test
    @DisplayName("현재 트렌드 유형이 없어도 저장한 트렌드를 빈 유형 배열로 유지한다")
    void keepsSavedTrendWithoutCurrentType() {
        // given
        Trend trend = TrendFixture.trend();
        ReflectionTestUtils.setField(trend, "trendTypes", new TrendType[0]);
        SavedTrend savedTrend = savedTrend(trend, 15L);
        PageRequest pageable = PageRequest.of(0, 20);
        AnalysisWindow window = AnalysisWindow.completed(AnalysisPeriod.HOURS_24, clock);
        given(savedTrendRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(1L, pageable))
                .willReturn(new PageImpl<>(List.of(savedTrend), pageable, 1));
        given(keywordMetricRepository.findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                List.of(81L), AnalysisPeriod.HOURS_24,
                window.getRecentStart(), window.getRecentEnd())).willReturn(List.of());

        // when
        SavedTrendListResponse response = service.getSavedTrends(1L, AnalysisPeriod.HOURS_24, 0, 20);

        // then
        assertThat(response.content()).singleElement().satisfies(item -> {
            assertThat(item.trendTypes()).isEmpty();
            assertThat(item.mentionCount()).isNull();
            assertThat(item.growthRate()).isNull();
        });
    }

    @Test
    @DisplayName("저장한 트렌드가 없으면 빈 페이지를 반환하고 지표를 조회하지 않는다")
    void returnsEmptyPageWithoutMetricQuery() {
        // given
        PageRequest pageable = PageRequest.of(0, 20);
        given(savedTrendRepository.findAllByMemberIdOrderByCreatedAtDescIdDesc(1L, pageable))
                .willReturn(new PageImpl<>(List.of(), pageable, 0));

        // when
        SavedTrendListResponse response = service.getSavedTrends(1L, AnalysisPeriod.DAYS_30, 0, 20);

        // then
        assertThat(response.content()).isEmpty();
        assertThat(response.hasNext()).isFalse();
        then(keywordMetricRepository).should(never())
                .findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                        org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                        org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    private SavedTrend savedTrend(Trend trend, Long id) {
        Member member = Member.create("member@example.com", "password", "member");
        ReflectionTestUtils.setField(member, "id", 1L);
        SavedTrend savedTrend = SavedTrend.save(member, trend);
        ReflectionTestUtils.setField(savedTrend, "id", id);
        ReflectionTestUtils.setField(savedTrend, "createdAt",
                TrendFixture.END.plusHours(id));
        return savedTrend;
    }
}
