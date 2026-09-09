package com.forever102.member.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.service.MemberInterestKeywordService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/members/me")
@RequiredArgsConstructor
public class MemberController {

    private final MemberInterestKeywordService interestKeywordService;

    @PostMapping("/interest-keywords")
    @ResponseStatus(HttpStatus.CREATED)
    public BaseResponse<InterestKeywordRegisterResponse> registerInterestKeyword(
            @AuthenticationPrincipal Long memberId,
            @Valid @RequestBody InterestKeywordRegisterRequest request
    ) {
        return BaseResponse.success(interestKeywordService.register(memberId, request));
    }
}
