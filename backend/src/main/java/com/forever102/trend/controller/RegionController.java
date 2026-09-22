package com.forever102.trend.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.dto.CountryRegionResponse;
import com.forever102.trend.dto.CountryTrendResponse;
import com.forever102.trend.service.CountryTrendService;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 나라를 축으로 보는 조회입니다. /trends 아래가 아니라 따로 둔 것은 트렌드를 고르기 전에도
 * 부를 수 있어야 하기 때문입니다. 나라 목록이 있어야 나라를 고를 수 있습니다.
 */
@RestController
@RequestMapping("/regions")
@RequiredArgsConstructor
@Validated
public class RegionController {

    private final CountryTrendService countryTrendService;

    @GetMapping
    public BaseResponse<CountryRegionResponse> getRegions(
            @RequestParam Domain domain,
            @RequestParam String period
    ) {
        return BaseResponse.success(
                countryTrendService.getCountries(domain, AnalysisPeriod.from(period)));
    }

    @GetMapping("/{countryCode}/trends")
    public BaseResponse<CountryTrendResponse> getCountryTrends(
            @PathVariable String countryCode,
            @RequestParam Domain domain,
            @RequestParam String period,
            @RequestParam(defaultValue = "5") @Positive int size
    ) {
        return BaseResponse.success(countryTrendService.getCountryTrends(
                domain, countryCode, AnalysisPeriod.from(period), size));
    }
}
