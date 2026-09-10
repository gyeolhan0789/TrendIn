package com.forever102.member.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;

import com.forever102.member.domain.Member;
import com.forever102.member.domain.SavedTrend;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.dto.SavedTrendRegisterRequest;
import com.forever102.member.repository.MemberRepository;
import com.forever102.member.repository.SavedTrendRepository;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.ZoneOffset;
import java.sql.SQLException;
import java.util.List;
import org.hibernate.exception.ConstraintViolationException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SavedTrendServiceTest {

    @Mock SavedTrendRepository savedTrendRepository;
    @Mock MemberRepository memberRepository;
    @Mock TrendRepository trendRepository;
    @Mock KeywordMetricRepository keywordMetricRepository;

    private SavedTrendService service;
    private Clock clock;

    @BeforeEach
    void setUp() {
        clock = Clock.fixed(TrendFixture.END.plusHours(12).toInstant(), ZoneOffset.UTC);
        service = new SavedTrendService(savedTrendRepository, memberRepository, trendRepository,
                keywordMetricRepository, clock);
    }

    @Test
    @DisplayName("로그인한 회원이 존재하는 트렌드를 저장한다")
    void registersSavedTrend() {
        // given
        Member member = Member.create("member@example.com", "password", "member");
        ReflectionTestUtils.setField(member, "id", 1L);
        Trend trend = TrendFixture.trend();
        given(savedTrendRepository.existsByMemberIdAndTrendId(1L, 101L)).willReturn(false);
        given(memberRepository.findById(1L)).willReturn(java.util.Optional.of(member));
        given(trendRepository.findById(101L)).willReturn(java.util.Optional.of(trend));
        given(savedTrendRepository.saveAndFlush(any(SavedTrend.class))).willAnswer(invocation -> {
            SavedTrend savedTrend = invocation.getArgument(0);
            ReflectionTestUtils.setField(savedTrend, "id", 15L);
            ReflectionTestUtils.setField(savedTrend, "createdAt", TrendFixture.END.plusHours(9));
            return savedTrend;
        });

        // when
        var response = service.register(1L, new SavedTrendRegisterRequest(101L));

        // then
        assertThat(response.savedTrendId()).isEqualTo(15L);
        assertThat(response.trendId()).isEqualTo(101L);
        assertThat(response.savedAt()).isEqualTo(TrendFixture.END.plusHours(9));
    }

    @Test
    @DisplayName("이미 저장한 트렌드는 중복 저장할 수 없다")
    void rejectsDuplicateSavedTrend() {
        // given
        given(savedTrendRepository.existsByMemberIdAndTrendId(1L, 101L)).willReturn(true);

        // when & then
        assertThatThrownBy(() -> service.register(1L, new SavedTrendRegisterRequest(101L)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.SAVED_TREND_ALREADY_EXISTS);
        then(memberRepository).should(never()).findById(any());
        then(trendRepository).should(never()).findById(any());
    }

    @Test
    @DisplayName("존재하지 않는 트렌드는 저장할 수 없다")
    void rejectsUnknownTrend() {
        // given
        Member member = Member.create("member@example.com", "password", "member");
        given(savedTrendRepository.existsByMemberIdAndTrendId(1L, 999L)).willReturn(false);
        given(memberRepository.findById(1L)).willReturn(java.util.Optional.of(member));
        given(trendRepository.findById(999L)).willReturn(java.util.Optional.empty());

        // when & then
        assertThatThrownBy(() -> service.register(1L, new SavedTrendRegisterRequest(999L)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.TREND_NOT_FOUND);
    }

    @Test
    @DisplayName("동시 저장으로 유니크 제약을 위반하면 중복 저장 예외가 발생한다")
    void translatesUniqueConstraintViolation() {
        // given
        Member member = Member.create("member@example.com", "password", "member");
        Trend trend = TrendFixture.trend();
        given(memberRepository.findById(1L)).willReturn(java.util.Optional.of(member));
        given(trendRepository.findById(101L)).willReturn(java.util.Optional.of(trend));
        given(savedTrendRepository.saveAndFlush(any(SavedTrend.class)))
                .willThrow(uniqueConstraintViolation());

        // when & then
        assertThatThrownBy(() -> service.register(1L, new SavedTrendRegisterRequest(101L)))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.SAVED_TREND_ALREADY_EXISTS);
    }

    @Test
    @DisplayName("다른 DB 무결성 위반은 중복 저장 예외로 변환하지 않는다")
    void doesNotTranslateOtherIntegrityViolation() {
        // given
        Member member = Member.create("member@example.com", "password", "member");
        Trend trend = TrendFixture.trend();
        DataIntegrityViolationException violation = new DataIntegrityViolationException(
                "foreign key violation",
                new ConstraintViolationException("foreign key violation", new SQLException(), "fk_trend"));
        given(memberRepository.findById(1L)).willReturn(java.util.Optional.of(member));
        given(trendRepository.findById(101L)).willReturn(java.util.Optional.of(trend));
        given(savedTrendRepository.saveAndFlush(any(SavedTrend.class))).willThrow(violation);

        // when & then
        assertThatThrownBy(() -> service.register(1L, new SavedTrendRegisterRequest(101L)))
                .isSameAs(violation);
    }

    @Test
    @DisplayName("로그인한 회원이 본인의 저장 트렌드를 해제한다")
    void deletesOwnedSavedTrend() {
        // given
        SavedTrend savedTrend = savedTrend(TrendFixture.trend(), 15L);
        given(savedTrendRepository.findByIdAndMemberId(15L, 1L))
                .willReturn(java.util.Optional.of(savedTrend));

        // when
        service.delete(1L, 15L);

        // then
        then(savedTrendRepository).should().delete(savedTrend);
        then(trendRepository).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("존재하지 않거나 다른 회원이 저장한 항목은 해제할 수 없다")
    void rejectsUnownedSavedTrendDeletion() {
        // given
        given(savedTrendRepository.findByIdAndMemberId(15L, 1L))
                .willReturn(java.util.Optional.empty());

        // when & then
        assertThatThrownBy(() -> service.delete(1L, 15L))
                .isInstanceOf(BusinessException.class)
                .extracting("errorCode").isEqualTo(ErrorCode.SAVED_TREND_NOT_FOUND);
        then(savedTrendRepository).should(never()).delete(any());
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

    private DataIntegrityViolationException uniqueConstraintViolation() {
        return new DataIntegrityViolationException(
                "unique constraint violation",
                new ConstraintViolationException(
                        "unique constraint violation",
                        new SQLException(),
                        SavedTrend.UNIQUE_MEMBER_TREND_CONSTRAINT));
    }
}
