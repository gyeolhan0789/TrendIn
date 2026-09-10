package com.forever102.trend.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.domain.Domain;
import com.forever102.trend.dto.KeywordSearchResponse;
import com.forever102.trend.service.KeywordService;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/keywords")
@RequiredArgsConstructor
public class KeywordController {

    private final KeywordService keywordService;

    @GetMapping("/search")
    public BaseResponse<KeywordSearchResponse> search(
            @RequestParam @NotBlank String query,
            @RequestParam(required = false) Domain domain,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Positive int size
    ) {
        return BaseResponse.success(keywordService.search(query, domain, page, size));
    }
}
