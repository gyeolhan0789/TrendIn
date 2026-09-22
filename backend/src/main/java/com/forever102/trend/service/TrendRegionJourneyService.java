package com.forever102.trend.service;

import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.AnalysisWindow;
import com.forever102.trend.domain.CountryNames;
import com.forever102.trend.domain.Trend;
import com.forever102.trend.dto.TrendRegionJourneyResponse;
import com.forever102.trend.dto.TrendRegionJourneyResponse.JourneyItemResponse;
import com.forever102.trend.repository.KeywordCountryDailyMetricRepository;
import com.forever102.trend.repository.TrendRepository;
import java.time.Clock;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class TrendRegionJourneyService {

    private final TrendRepository trendRepository;
    private final KeywordCountryDailyMetricRepository countryMetricRepository;
    private final Clock trendClock;

    public TrendRegionJourneyResponse getJourney(Long trendId) {
        Trend trend = trendRepository.findById(trendId)
                .orElseThrow(() -> new BusinessException(ErrorCode.TREND_NOT_FOUND));
        AnalysisWindow window = AnalysisWindow.completed(AnalysisPeriod.DAYS_30, trendClock);
        LocalDate startDate = window.getRecentStart().toLocalDate();
        LocalDate endDate = window.getRecentEnd().toLocalDate();

        var detections = countryMetricRepository.findCountryFirstDetections(
                trend.getKeyword().getId(), startDate, endDate);
        List<JourneyItemResponse> regions = new ArrayList<>();
        for (int index = 0; index < detections.size(); index++) {
            var detection = detections.get(index);
            regions.add(new JourneyItemResponse(detection.getCountryCode(),
                    CountryNames.of(detection.getCountryCode()), detection.getFirstDetectedDate(), index + 1));
        }
        return TrendRegionJourneyResponse.of(trendId, startDate, endDate, regions);
    }
}
