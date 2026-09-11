package com.forever102.member.controller;

import com.forever102.global.response.BaseResponse;
import com.forever102.member.dto.DomainResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/domains")
public class DomainController {

    @GetMapping
    public BaseResponse<List<DomainResponse>> getDomains() {
        return BaseResponse.success(DomainResponse.all());
    }
}
