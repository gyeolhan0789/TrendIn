package com.forever102.trend.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.dto.TrendContentResponse;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.dto.TrendHistoryResponse;
import com.forever102.trend.dto.TrendListResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendService;
import jakarta.validation.constraints.Min;
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

    @GetMapping
    public BaseResponse<TrendListResponse> getTrends(
            @RequestParam Domain domain,
            @RequestParam TrendType type,
            @RequestParam String period,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Positive int size
    ) {
        return BaseResponse.success(
                trendService.getTrends(domain, type, AnalysisPeriod.from(period), page, size));
    }

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

    @GetMapping("/{trendId}/contents")
    public BaseResponse<TrendContentResponse> getTrendContents(
            @PathVariable @Positive Long trendId,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "10") @Positive int size
    ) {
        return BaseResponse.success(trendService.getTrendContents(trendId, page, size));
    }
}
