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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.global.config.SecurityTestConfig;
import com.forever102.trend.dto.TrendRegionJourneyResponse;
import com.forever102.trend.dto.TrendRegionJourneyResponse.JourneyItemResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendRegionHistoryService;
import com.forever102.trend.service.TrendRegionJourneyService;
import com.forever102.trend.service.TrendRegionService;
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
class TrendRegionJourneyControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean TrendService trendService;
    @MockitoBean TrendHistoryService trendHistoryService;
    @MockitoBean TrendRegionService trendRegionService;
    @MockitoBean TrendRegionHistoryService trendRegionHistoryService;
    @MockitoBean TrendRegionJourneyService trendRegionJourneyService;

    @Test
    @WithMockUser
    @DisplayName("국가별 최초 관측 흐름을 반환하고 문서화한다")
    void returnsTrendRegionJourney() throws Exception {
        LocalDate start = LocalDate.of(2026, 8, 1);
        LocalDate end = LocalDate.of(2026, 8, 31);
        given(trendRegionJourneyService.getJourney(101L))
                .willReturn(TrendRegionJourneyResponse.of(101L, start, end,
                        List.of(new JourneyItemResponse("FR", "프랑스",
                                        LocalDate.of(2026, 8, 3), 1),
                                new JourneyItemResponse("US", "미국",
                                        LocalDate.of(2026, 8, 7), 2))));

        mockMvc.perform(get("/trends/{trendId}/regions/journey", 101L)
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.period").value("30D"))
                .andExpect(jsonPath("$.data.regions[0].countryCode").value("FR"))
                .andExpect(jsonPath("$.data.regions[0].countryName").value("프랑스"))
                .andExpect(jsonPath("$.data.regions[0].firstDetectedDate").value("2026-08-03"))
                .andExpect(jsonPath("$.data.regions[0].order").value(1))
                .andDo(document("trends-regions-journey", preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.period").type(JsonFieldType.STRING).description("고정 조회 기간: 30D"),
                                fieldWithPath("data.timezone").type(JsonFieldType.STRING).description("집계 시간대"),
                                fieldWithPath("data.startDate").type(JsonFieldType.STRING).description("조회 시작일, 포함"),
                                fieldWithPath("data.endDate").type(JsonFieldType.STRING).description("조회 종료일, 미포함"),
                                fieldWithPath("data.regions").type(JsonFieldType.ARRAY).description("수집 데이터 기준 국가별 최초 관측 순서"),
                                fieldWithPath("data.regions[].countryCode").type(JsonFieldType.STRING).description("ISO 3166-1 alpha-2 국가 코드"),
                                fieldWithPath("data.regions[].countryName").type(JsonFieldType.STRING).description("사용자 표시용 한글 국가명"),
                                fieldWithPath("data.regions[].firstDetectedDate").type(JsonFieldType.STRING).description("조회 기간 내 최초 언급일"),
                                fieldWithPath("data.regions[].order").type(JsonFieldType.NUMBER).description("최초 관측 순서"))));
    }

    @Test
    @DisplayName("인증 없이 국가별 최초 관측 흐름을 요청하면 401을 반환한다")
    void blocksAnonymousJourney() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/regions/journey", 101L))
                .andExpect(status().isUnauthorized());
    }
}
