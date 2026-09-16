package com.forever102.trend.controller;

import static org.mockito.BDDMockito.given;
import static org.springframework.restdocs.headers.HeaderDocumentation.headerWithName;
import static org.springframework.restdocs.headers.HeaderDocumentation.requestHeaders;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders.get;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessRequest;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.restdocs.request.RequestDocumentation.parameterWithName;
import static org.springframework.restdocs.request.RequestDocumentation.pathParameters;
import static org.springframework.restdocs.request.RequestDocumentation.queryParameters;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.global.config.SecurityTestConfig;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.dto.TrendRegionResponse;
import com.forever102.trend.dto.TrendRegionResponse.RegionItemResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendRegionService;
import com.forever102.trend.service.TrendRegionHistoryService;
import com.forever102.trend.service.TrendRegionJourneyService;
import com.forever102.trend.service.TrendService;
import java.time.LocalDate;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TrendController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class TrendRegionControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean TrendService trendService;
    @MockitoBean TrendHistoryService trendHistoryService;
    @MockitoBean TrendRegionService trendRegionService;
    @MockitoBean TrendRegionHistoryService trendRegionHistoryService;
    @MockitoBean TrendRegionJourneyService trendRegionJourneyService;

    @Test
    @WithMockUser
    @DisplayName("국가별 관심도 순위와 한글 국가명을 반환하고 문서화한다")
    void returnsTrendRegions() throws Exception {
        LocalDate start = LocalDate.of(2026, 8, 24);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRegionService.getRegions(101L, AnalysisPeriod.DAYS_7))
                .willReturn(TrendRegionResponse.of(101L, AnalysisPeriod.DAYS_7, start, end,
                        List.of(new RegionItemResponse(1, "KR", "대한민국", 53L),
                                new RegionItemResponse(2, "US", "미국", 41L))));

        mockMvc.perform(get("/trends/{trendId}/regions", 101L)
                        .queryParam("period", "7D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.period").value("7D"))
                .andExpect(jsonPath("$.data.regions[0].countryCode").value("KR"))
                .andExpect(jsonPath("$.data.regions[0].countryName").value("대한민국"))
                .andExpect(jsonPath("$.data.regions[0].rank").value(1))
                .andDo(document("trends-regions", preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수")),
                        queryParameters(parameterWithName("period").description("필수 조회 기간: 24H, 7D")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.period").type(JsonFieldType.STRING).description("조회 기간"),
                                fieldWithPath("data.timezone").type(JsonFieldType.STRING).description("집계 시간대"),
                                fieldWithPath("data.startDate").type(JsonFieldType.STRING).description("조회 시작일, 포함"),
                                fieldWithPath("data.endDate").type(JsonFieldType.STRING).description("조회 종료일, 미포함"),
                                fieldWithPath("data.regions").type(JsonFieldType.ARRAY).description("국가별 관심도 순위"),
                                fieldWithPath("data.regions[].rank").type(JsonFieldType.NUMBER).description("관심도 순위"),
                                fieldWithPath("data.regions[].countryCode").type(JsonFieldType.STRING).description("ISO 3166-1 alpha-2 국가 코드"),
                                fieldWithPath("data.regions[].countryName").type(JsonFieldType.STRING).description("사용자 표시용 한글 국가명"),
                                fieldWithPath("data.regions[].mentionCount").type(JsonFieldType.NUMBER).description("조회 기간 언급량"))));
    }

    @Test
    @WithMockUser
    @DisplayName("국가별 관심도 순위 조회의 기간이 누락되면 400을 반환한다")
    void rejectsMissingRegionPeriod() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/regions", 101L))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("인증 없이 국가별 관심도 순위를 요청하면 401을 반환한다")
    void blocksAnonymousRegions() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/regions", 101L).queryParam("period", "7D"))
                .andExpect(status().isUnauthorized());
    }
}
