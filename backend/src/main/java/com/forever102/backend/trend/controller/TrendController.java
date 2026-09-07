package com.forever102.backend.trend.controller;

import com.forever102.backend.global.response.BaseResponse;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.service.TrendService;
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

    @GetMapping("/{trendId}")
    public BaseResponse<TrendDetailResponse> getTrendDetail(
            @PathVariable @Positive Long trendId,
            @RequestParam String period
    ) {
        return BaseResponse.success(trendService.getTrendDetail(trendId, AnalysisPeriod.from(period)));
    }
}
