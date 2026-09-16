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
import com.forever102.trend.dto.TrendRegionHistoryResponse;
import com.forever102.trend.dto.TrendRegionHistoryResponse.HistoryPointResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendRegionHistoryService;
import com.forever102.trend.service.TrendRegionJourneyService;
import com.forever102.trend.service.TrendRegionService;
import com.forever102.trend.service.TrendService;
import java.time.OffsetDateTime;
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
class TrendRegionHistoryControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean TrendService trendService;
    @MockitoBean TrendHistoryService trendHistoryService;
    @MockitoBean TrendRegionService trendRegionService;
    @MockitoBean TrendRegionHistoryService trendRegionHistoryService;
    @MockitoBean TrendRegionJourneyService trendRegionJourneyService;

    @Test
    @WithMockUser
    @DisplayName("특정 국가 관심도 일 시계열을 반환하고 문서화한다")
    void returnsTrendRegionHistory() throws Exception {
        OffsetDateTime start = OffsetDateTime.parse("2026-08-24T00:00:00+09:00");
        OffsetDateTime end = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
        given(trendRegionHistoryService.getHistory(101L, "KR", AnalysisPeriod.DAYS_7))
                .willReturn(TrendRegionHistoryResponse.of(101L, "KR", "대한민국",
                        AnalysisPeriod.DAYS_7, start, end,
                        List.of(new HistoryPointResponse(start, start.plusDays(1), 7L),
                                new HistoryPointResponse(start.plusDays(1), start.plusDays(2), 0L))));

        mockMvc.perform(get("/trends/{trendId}/regions/{countryCode}/history", 101L, "KR")
                        .queryParam("period", "7D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.countryCode").value("KR"))
                .andExpect(jsonPath("$.data.countryName").value("대한민국"))
                .andExpect(jsonPath("$.data.history[0].mentionCount").value(7))
                .andDo(document("trends-region-history", preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(
                                parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수"),
                                parameterWithName("countryCode").description("ISO 3166-1 alpha-2 국가 코드")),
                        queryParameters(parameterWithName("period").description("필수 조회 기간: 24H, 7D")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.countryCode").type(JsonFieldType.STRING).description("국가 코드"),
                                fieldWithPath("data.countryName").type(JsonFieldType.STRING).description("사용자 표시용 한글 국가명"),
                                fieldWithPath("data.period").type(JsonFieldType.STRING).description("조회 기간"),
                                fieldWithPath("data.timezone").type(JsonFieldType.STRING).description("집계 시간대"),
                                fieldWithPath("data.startAt").type(JsonFieldType.STRING).description("조회 시작"),
                                fieldWithPath("data.endAt").type(JsonFieldType.STRING).description("조회 종료"),
                                fieldWithPath("data.history").type(JsonFieldType.ARRAY).description("국가 관심도 시계열"),
                                fieldWithPath("data.history[].bucketStart").type(JsonFieldType.STRING).description("일 버킷 시작"),
                                fieldWithPath("data.history[].bucketEnd").type(JsonFieldType.STRING).description("일 버킷 종료"),
                                fieldWithPath("data.history[].mentionCount").type(JsonFieldType.NUMBER).description("언급량"))));
    }

    @Test
    @WithMockUser
    @DisplayName("국가 관심도 추이 조회의 기간이 누락되면 400을 반환한다")
    void rejectsMissingPeriod() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/regions/{countryCode}/history", 101L, "KR"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("인증 없이 국가 관심도 추이를 요청하면 401을 반환한다")
    void blocksAnonymousHistory() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/regions/{countryCode}/history", 101L, "KR")
                        .queryParam("period", "7D"))
                .andExpect(status().isUnauthorized());
    }
}
