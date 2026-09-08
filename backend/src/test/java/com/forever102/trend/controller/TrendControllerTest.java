package com.forever102.trend.controller;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
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
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.dto.TrendHistoryResponse;
import com.forever102.trend.dto.TrendHistoryResponse.HistoryPointResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendService;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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
class TrendControllerTest {

    @Autowired MockMvc mockMvc;
    @MockitoBean TrendService trendService;
    @MockitoBean TrendHistoryService trendHistoryService;

    @Test
    @WithMockUser
    @DisplayName("최신 명세의 트렌드 상세 응답을 반환하고 문서화한다")
    void returnsTrendDetail() throws Exception {
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7))
                .willReturn(TrendDetailResponse.from(trend,
                        TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123), AnalysisPeriod.DAYS_7));

        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "7D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value(nullValue()))
                .andExpect(jsonPath("$.data.domain.code").value("FASHION"))
                .andExpect(jsonPath("$.data.trendTypes[0]").value("RISING"))
                .andExpect(jsonPath("$.data.analysisWindow.recentStart").value("2026-08-24T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.growthRate").value(249.6))
                .andExpect(jsonPath("$.data.summary").isString())
                .andExpect(jsonPath("$.data.reason").isString())
                .andExpect(jsonPath("$.data.firstDetectedAt").doesNotExist())
                .andExpect(jsonPath("$.data.trendType").doesNotExist())
                .andExpect(jsonPath("$.data.aiAnalysis").doesNotExist())
                .andExpect(jsonPath("$.data.evidence").doesNotExist())
                .andDo(document("trends-detail", preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수")),
                        queryParameters(parameterWithName("period").description("필수 조회 기간: 24H, 7D, 30D")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.keywordId").type(JsonFieldType.NUMBER).description("키워드 ID"),
                                fieldWithPath("data.keyword").type(JsonFieldType.STRING).description("키워드"),
                                fieldWithPath("data.description").type(JsonFieldType.STRING).description("짧은 설명"),
                                fieldWithPath("data.domain.code").type(JsonFieldType.STRING).description("분야 코드"),
                                fieldWithPath("data.domain.name").type(JsonFieldType.STRING).description("분야 이름"),
                                fieldWithPath("data.trendTypes").type(JsonFieldType.ARRAY).description("트렌드 유형 목록"),
                                fieldWithPath("data.mentionCount").type(JsonFieldType.NUMBER).description("요청 기간 언급량"),
                                fieldWithPath("data.previousMentionCount").type(JsonFieldType.NUMBER).description("직전 기간 언급량"),
                                fieldWithPath("data.growthAmount").type(JsonFieldType.NUMBER).description("언급 증가량"),
                                fieldWithPath("data.growthRate").type(JsonFieldType.NUMBER).description("언급 증가율"),
                                fieldWithPath("data.analysisWindow.recentStart").type(JsonFieldType.STRING).description("최근 구간 시작"),
                                fieldWithPath("data.analysisWindow.recentEnd").type(JsonFieldType.STRING).description("최근 구간 종료"),
                                fieldWithPath("data.analysisWindow.previousStart").type(JsonFieldType.STRING).description("직전 구간 시작"),
                                fieldWithPath("data.analysisWindow.previousEnd").type(JsonFieldType.STRING).description("직전 구간 종료"),
                                fieldWithPath("data.summary").type(JsonFieldType.STRING).description("상세 AI 요약"),
                                fieldWithPath("data.reason").type(JsonFieldType.STRING).description("주목 이유"))));
    }

    @Test
    @WithMockUser
    @DisplayName("요청 기간 지표가 없으면 지표 필드는 null이고 트렌드 정보는 유지한다")
    void returnsNullMetricFields() throws Exception {
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30))
                .willReturn(TrendDetailResponse.from(trend, null, AnalysisPeriod.DAYS_30));

        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "30D"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trendTypes[0]").value("RISING"))
                .andExpect(jsonPath("$.data.mentionCount").value(nullValue()))
                .andExpect(jsonPath("$.data.analysisWindow").value(nullValue()))
                .andExpect(jsonPath("$.data.summary").isString());
    }

    @Test
    @WithMockUser
    @DisplayName("기간별 관심도 시계열을 bucketStart와 bucketEnd로 반환하고 문서화한다")
    void returnsTrendHistory() throws Exception {
        var start = OffsetDateTime.parse("2026-08-01T00:00:00+09:00");
        var end = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
        given(trendHistoryService.getHistory(101L, AnalysisPeriod.DAYS_30))
                .willReturn(TrendHistoryResponse.of(101L, AnalysisPeriod.DAYS_30, start, end,
                        List.of(new HistoryPointResponse(start, start.plusDays(3), 120L),
                                new HistoryPointResponse(start.plusDays(3), start.plusDays(6), 145L))));

        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "30D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.period").value("30D"))
                .andExpect(jsonPath("$.data.timezone").value("Asia/Seoul"))
                .andExpect(jsonPath("$.data.dataStatus").doesNotExist())
                .andExpect(jsonPath("$.data.history[0].bucketStart").value("2026-08-01T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.history[0].bucketEnd").value("2026-08-04T00:00:00+09:00"))
                .andDo(document("trends-history", preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수")),
                        queryParameters(parameterWithName("period").description("필수 조회 기간: 24H, 7D, 30D")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.period").type(JsonFieldType.STRING).description("조회 기간"),
                                fieldWithPath("data.timezone").type(JsonFieldType.STRING).description("시간대"),
                                fieldWithPath("data.startAt").type(JsonFieldType.STRING).description("조회 시작"),
                                fieldWithPath("data.endAt").type(JsonFieldType.STRING).description("조회 종료"),
                                fieldWithPath("data.history").type(JsonFieldType.ARRAY).description("시계열"),
                                fieldWithPath("data.history[].bucketStart").type(JsonFieldType.STRING).description("버킷 시작"),
                                fieldWithPath("data.history[].bucketEnd").type(JsonFieldType.STRING).description("버킷 종료"),
                                fieldWithPath("data.history[].mentionCount").type(JsonFieldType.NUMBER).description("언급량"))));
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"24H", "7D", "30D"})
    void acceptsAllowedPeriods(String period) throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", period))
                .andExpect(status().isOk());
    }

    @Test
    @WithMockUser
    void rejectsMissingPeriods() throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isBadRequest())
                .andDo(document("trends-detail-invalid-period", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
        mockMvc.perform(get("/trends/{trendId}/history", 101L)).andExpect(status().isBadRequest());
        then(trendService).shouldHaveNoInteractions();
        then(trendHistoryService).shouldHaveNoInteractions();
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"0", "-1", "abc", "9223372036854775808"})
    void rejectsInvalidTrendId(String trendId) throws Exception {
        mockMvc.perform(get("/trends/{trendId}", trendId).queryParam("period", "24H"))
                .andExpect(status().isBadRequest())
                .andDo(document("trends-detail-invalid-id", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    void returnsNotFound() throws Exception {
        given(trendService.getTrendDetail(999L, AnalysisPeriod.HOURS_24))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));
        mockMvc.perform(get("/trends/{trendId}", 999L).queryParam("period", "24H"))
                .andExpect(status().isNotFound())
                .andDo(document("trends-detail-not-found", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
    }

    @Test
    void blocksAnonymousRequests() throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "24H"))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "24H"))
                .andExpect(status().isUnauthorized());
    }
}
