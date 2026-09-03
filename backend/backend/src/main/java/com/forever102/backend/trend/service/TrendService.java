package com.forever102.backend.trend.service;

import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.domain.Trend;
import com.forever102.backend.trend.domain.TrendAnalysis;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import com.forever102.backend.trend.repository.TrendAnalysisRepository;
import com.forever102.backend.trend.repository.TrendRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendService {

    private final TrendRepository trendRepository;
    private final TrendAnalysisRepository trendAnalysisRepository;

    public TrendDetailResponse getTrendDetail(Long trendId) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        TrendAnalysis analysis = trendAnalysisRepository
                .findFirstByTrendIdOrderByAnalyzedAtDescIdDesc(trendId).orElse(null);
        return TrendDetailResponse.from(trend, analysis);
    }
}
