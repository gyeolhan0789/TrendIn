package com.forever102.member.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.domain.Member;
import com.forever102.member.domain.SavedTrend;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.dto.SavedTrendRegisterRequest;
import com.forever102.member.dto.SavedTrendRegisterResponse;
import com.forever102.member.repository.MemberRepository;
import com.forever102.member.repository.SavedTrendRepository;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.KeywordMetric;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.repository.KeywordMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.hibernate.exception.ConstraintViolationException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class SavedTrendService {

    private final SavedTrendRepository savedTrendRepository;
    private final MemberRepository memberRepository;
    private final TrendRepository trendRepository;
    private final KeywordMetricRepository keywordMetricRepository;
    private final Clock trendClock;

    public SavedTrendListResponse getSavedTrends(
            Long memberId,
            AnalysisPeriod period,
            int page,
            int size
    ) {
        Page<SavedTrend> savedTrends = savedTrendRepository
                .findAllByMemberIdOrderByCreatedAtDescIdDesc(memberId, PageRequest.of(page, size));
        if (savedTrends.isEmpty()) {
            return SavedTrendListResponse.from(savedTrends, Map.of());
        }

        AnalysisWindow window = AnalysisWindow.completed(period, trendClock);
        Map<Long, KeywordMetric> metricsByKeywordId = keywordMetricRepository
                .findByKeywordIdInAndPeriodAndPeriodStartAndPeriodEnd(
                        savedTrends.stream()
                                .map(savedTrend -> savedTrend.getTrend().getKeyword().getId())
                                .toList(),
                        period, window.getRecentStart(), window.getRecentEnd())
                .stream()
                .collect(Collectors.toMap(metric -> metric.getKeyword().getId(), Function.identity()));
        return SavedTrendListResponse.from(savedTrends, metricsByKeywordId);
    }

    @Transactional
    public SavedTrendRegisterResponse register(Long memberId, SavedTrendRegisterRequest request) {
        Long trendId = request.trendId();
        if (savedTrendRepository.existsByMemberIdAndTrendId(memberId, trendId)) {
            throw new BusinessException(ErrorCode.SAVED_TREND_ALREADY_EXISTS);
        }

        Member member = memberRepository.findById(memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.MEMBER_NOT_FOUND));
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        return SavedTrendRegisterResponse.from(save(SavedTrend.save(member, trend)));
    }

    @Transactional
    public void delete(Long memberId, Long savedTrendId) {
        SavedTrend savedTrend = savedTrendRepository.findByIdAndMemberId(savedTrendId, memberId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SAVED_TREND_NOT_FOUND));
        savedTrendRepository.delete(savedTrend);
    }

    private SavedTrend save(SavedTrend savedTrend) {
        try {
            return savedTrendRepository.saveAndFlush(savedTrend);
        } catch (DataIntegrityViolationException e) {
            if (isSavedTrendUniqueViolation(e)) {
                throw new BusinessException(ErrorCode.SAVED_TREND_ALREADY_EXISTS);
            }
            throw e;
        }
    }

    private boolean isSavedTrendUniqueViolation(DataIntegrityViolationException exception) {
        Throwable cause = exception;
        while (cause != null) {
            if (cause instanceof ConstraintViolationException violation
                    && SavedTrend.UNIQUE_MEMBER_TREND_CONSTRAINT
                    .equalsIgnoreCase(violation.getConstraintName())) {
                return true;
            }
            cause = cause.getCause();
        }
        return false;
    }
}
