package com.forever102.member.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.dto.InterestKeywordResponse;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.member.domain.Domain;
import com.forever102.member.dto.RecommendedKeywordResponse;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.service.MemberInterestKeywordService;
import com.forever102.member.service.MemberService;
import com.forever102.member.service.SavedTrendService;
import com.forever102.trend.domain.AnalysisPeriod;
import jakarta.validation.constraints.Min;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/members/me")
@RequiredArgsConstructor
public class MemberController {

    private final MemberService memberService;
    private final MemberInterestKeywordService interestKeywordService;
    private final SavedTrendService savedTrendService;

    @GetMapping
    public BaseResponse<MemberInfoResponse> getMyInfo(@AuthenticationPrincipal Long memberId) {
        return BaseResponse.success(memberService.getMyInfo(memberId));
    }

    @PatchMapping
    public BaseResponse<MemberInfoResponse> updateMyInfo(
            @AuthenticationPrincipal Long memberId,
            @Valid @RequestBody MemberUpdateRequest request
    ) {
        return BaseResponse.success(memberService.updateMyInfo(memberId, request));
    }

    @PostMapping("/interest-keywords")
    @ResponseStatus(HttpStatus.CREATED)
    public BaseResponse<InterestKeywordRegisterResponse> registerInterestKeyword(
            @AuthenticationPrincipal Long memberId,
            @Valid @RequestBody InterestKeywordRegisterRequest request
    ) {
        return BaseResponse.success(interestKeywordService.register(memberId, request));
    }

    @GetMapping("/recommended-keywords")
    public BaseResponse<List<RecommendedKeywordResponse>> getRecommendedKeywords(
            @AuthenticationPrincipal Long memberId
    ) {
        return BaseResponse.success(interestKeywordService.getRecommendedKeywords(memberId));
    }

    @GetMapping("/interest-keywords")
    public BaseResponse<List<InterestKeywordResponse>> getInterestKeywords(
            @AuthenticationPrincipal Long memberId,
            @RequestParam(required = false) Domain domain
    ) {
        return BaseResponse.success(interestKeywordService.getInterestKeywords(memberId, domain));
    }

    @DeleteMapping("/interest-keywords/{interestKeywordId}")
    public BaseResponse<Void> deleteInterestKeyword(
            @AuthenticationPrincipal Long memberId,
            @PathVariable @Positive Long interestKeywordId
    ) {
        interestKeywordService.delete(memberId, interestKeywordId);
        return BaseResponse.success(null);
    }

    @GetMapping("/saved-trends")
    public BaseResponse<SavedTrendListResponse> getSavedTrends(
            @AuthenticationPrincipal Long memberId,
            @RequestParam(defaultValue = "24H") String period,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Positive int size
    ) {
        return BaseResponse.success(savedTrendService.getSavedTrends(
                memberId, AnalysisPeriod.from(period), page, size));
    }
}
