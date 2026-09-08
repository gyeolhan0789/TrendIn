package com.forever102.trend.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.dto.TrendHistoryResponse;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.service.TrendService;
import com.forever102.trend.service.TrendHistoryService;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/trends")
@RequiredArgsConstructor
public class TrendController {

    private final TrendService trendService;
    private final TrendHistoryService trendHistoryService;

    @GetMapping("/{trendId}")
    public BaseResponse<TrendDetailResponse> getTrendDetail(
            @PathVariable @Positive Long trendId,
            @RequestParam String period
    ) {
        return BaseResponse.success(trendService.getTrendDetail(trendId, AnalysisPeriod.from(period)));
    }

    @GetMapping("/{trendId}/history")
    public BaseResponse<TrendHistoryResponse> getTrendHistory(
            @PathVariable @Positive Long trendId,
            @RequestParam String period
    ) {
        return BaseResponse.success(trendHistoryService.getHistory(trendId, AnalysisPeriod.from(period)));
    }
}
