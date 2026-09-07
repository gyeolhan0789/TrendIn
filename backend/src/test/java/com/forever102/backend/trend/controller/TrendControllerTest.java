package com.forever102.backend.trend.controller;

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

import com.forever102.backend.global.config.SecurityTestConfig;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.domain.AnalysisPeriod;
import com.forever102.backend.trend.domain.TrendHistoryDataStatus;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import com.forever102.backend.trend.dto.TrendHistoryResponse;
import com.forever102.backend.trend.dto.TrendHistoryResponse.HistoryPointResponse;
import com.forever102.backend.trend.service.TrendHistoryService;
import com.forever102.backend.trend.service.TrendService;
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
    @DisplayName("관심도 시계열을 조회하고 문서화한다")
    void returnsTrendHistory() throws Exception {
        var start = OffsetDateTime.parse("2026-08-24T00:00:00+09:00");
        var end = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
        given(trendHistoryService.getHistory(101L, AnalysisPeriod.DAYS_7))
                .willReturn(TrendHistoryResponse.of(101L, AnalysisPeriod.DAYS_7, start, end,
                        TrendHistoryDataStatus.AVAILABLE,
                        List.of(new HistoryPointResponse(start, 40L),
                                new HistoryPointResponse(start.plusDays(1), 0L),
                                new HistoryPointResponse(start.plusDays(2), 0L))));

        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "7D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.period").value("7D"))
                .andExpect(jsonPath("$.data.timezone").value("Asia/Seoul"))
                .andExpect(jsonPath("$.data.startAt").value("2026-08-24T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.endAt").value("2026-08-31T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.dataStatus").value("AVAILABLE"))
                .andExpect(jsonPath("$.data.history[1].mentionCount").value(0))
                .andExpect(jsonPath("$.data.history[2].mentionCount").value(0))
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
                                fieldWithPath("data.startAt").type(JsonFieldType.STRING).description("완료 구간 시작"),
                                fieldWithPath("data.endAt").type(JsonFieldType.STRING).description("완료 구간 종료. 미포함"),
                                fieldWithPath("data.dataStatus").type(JsonFieldType.STRING).description("AVAILABLE 또는 NO_DATA"),
                                fieldWithPath("data.history").type(JsonFieldType.ARRAY).description("오름차순 시계열"),
                                fieldWithPath("data.history[].timestamp").type(JsonFieldType.STRING).description("버킷 시작 시각"),
                                fieldWithPath("data.history[].mentionCount").type(JsonFieldType.NUMBER)
                                        .description("언급량. 해당 버킷에 언급 데이터가 없으면 0"))));
    }

    @Test
    @WithMockUser
    @DisplayName("시계열 데이터가 없으면 200과 NO_DATA를 반환한다")
    void returnsNoHistoryData() throws Exception {
        var start = OffsetDateTime.parse("2026-08-30T00:00:00+09:00");
        var end = start.plusDays(1);
        given(trendHistoryService.getHistory(101L, AnalysisPeriod.HOURS_24))
                .willReturn(TrendHistoryResponse.of(101L, AnalysisPeriod.HOURS_24, start, end,
                        TrendHistoryDataStatus.NO_DATA, List.of()));

        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "24H"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.dataStatus").value("NO_DATA"))
                .andExpect(jsonPath("$.data.history").isEmpty());
    }

    @Test
    @WithMockUser
    @DisplayName("시계열 조회 기간이 누락되거나 잘못되면 400을 반환한다")
    void rejectsInvalidHistoryPeriod() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/history", 101L))
                .andExpect(status().isBadRequest());
        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "1D"))
                .andExpect(status().isBadRequest());
        then(trendHistoryService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("존재하지 않는 트렌드의 시계열 조회는 404를 반환한다")
    void returnsNotFoundForHistory() throws Exception {
        given(trendHistoryService.getHistory(999L, AnalysisPeriod.DAYS_30))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));
        mockMvc.perform(get("/trends/{trendId}/history", 999L).queryParam("period", "30D"))
                .andExpect(status().isNotFound());
    }

    @Test
    @DisplayName("인증 없이 시계열을 요청하면 401을 반환한다")
    void existingSecurityBlocksAnonymousHistoryRequest() throws Exception {
        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "7D"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
        then(trendHistoryService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("필수 기간을 전달하면 해당 기간 상세 결과와 최신 AI 분석을 반환하고 문서화한다")
    void returnsRequestedPeriodDetail() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7))
                .willReturn(TrendDetailResponse.from(trend,
                        TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123),
                        TrendFixture.aiAnalysis(trend)));
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "7D")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value(nullValue()))
                .andExpect(jsonPath("$.data.domain.code").value("FASHION"))
                .andExpect(jsonPath("$.data.analysisWindow.recentStart").value("2026-08-24T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.growthRate").value(249.6))
                .andExpect(jsonPath("$.data.aiAnalysis.sourceContentIds[0]").value(301))
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
                                fieldWithPath("data.description").type(JsonFieldType.STRING).optional().description("짧은 설명"),
                                fieldWithPath("data.firstDetectedAt").type(JsonFieldType.STRING).description("최초 탐지 시각"),
                                fieldWithPath("data.domain.code").type(JsonFieldType.STRING).description("DEVELOP 또는 FASHION"),
                                fieldWithPath("data.domain.name").type(JsonFieldType.STRING).description("분야 표시명"),
                                fieldWithPath("data.trendType").type(JsonFieldType.STRING).optional().description("요청 기간 트렌드 유형"),
                                fieldWithPath("data.mentionCount").type(JsonFieldType.NUMBER).optional().description("요청 기간 언급량"),
                                fieldWithPath("data.previousMentionCount").type(JsonFieldType.NUMBER).optional().description("직전 동기간 언급량"),
                                fieldWithPath("data.growthAmount").type(JsonFieldType.NUMBER).optional().description("언급 증가량"),
                                fieldWithPath("data.growthRate").type(JsonFieldType.NUMBER).optional().description("증가율. 직전 언급량이 0이면 null"),
                                fieldWithPath("data.analysisWindow").type(JsonFieldType.OBJECT).optional().description("Asia/Seoul 기준 분석 구간"),
                                fieldWithPath("data.analysisWindow.recentStart").type(JsonFieldType.STRING).description("최근 구간 시작"),
                                fieldWithPath("data.analysisWindow.recentEnd").type(JsonFieldType.STRING).description("최근 구간 종료"),
                                fieldWithPath("data.analysisWindow.previousStart").type(JsonFieldType.STRING).description("직전 구간 시작"),
                                fieldWithPath("data.analysisWindow.previousEnd").type(JsonFieldType.STRING).description("직전 구간 종료"),
                                fieldWithPath("data.analyzedAt").type(JsonFieldType.STRING).optional().description("기간 지표 분석 시각"),
                                fieldWithPath("data.evidence").type(JsonFieldType.OBJECT).optional().description("기간별 판정 근거"),
                                fieldWithPath("data.evidence.ruleVersion").type(JsonFieldType.STRING).optional().description("규칙 버전"),
                                fieldWithPath("data.evidence.ruleDescription").type(JsonFieldType.STRING).optional().description("규칙 설명"),
                                fieldWithPath("data.evidence.appliedThresholds").type(JsonFieldType.OBJECT).optional().description("숫자 임계값"),
                                fieldWithPath("data.evidence.appliedThresholds.*").type(JsonFieldType.NUMBER).description("저장된 임계값"),
                                fieldWithPath("data.evidence.dataCoverage").type(JsonFieldType.STRING).optional().description("데이터 완전성"),
                                fieldWithPath("data.aiAnalysis").type(JsonFieldType.OBJECT).optional().description("기간과 무관한 최신 AI 분석"),
                                fieldWithPath("data.aiAnalysis.status").type(JsonFieldType.STRING).description("AI 분석 상태"),
                                fieldWithPath("data.aiAnalysis.summary").type(JsonFieldType.STRING).optional().description("AI 요약"),
                                fieldWithPath("data.aiAnalysis.reason").type(JsonFieldType.STRING).optional().description("AI 분석 이유"),
                                fieldWithPath("data.aiAnalysis.sourceContentIds").type(JsonFieldType.ARRAY).description("AI 입력 콘텐츠 ID"),
                                fieldWithPath("data.aiAnalysis.generatedAt").type(JsonFieldType.STRING).description("AI 생성 시각"))));
    }

    @Test
    @WithMockUser
    @DisplayName("요청 기간 지표가 없으면 200과 null 지표 및 최신 AI 분석을 반환한다")
    void returnsNullPeriodMetricWithOk() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30))
                .willReturn(TrendDetailResponse.from(trend, null, TrendFixture.aiAnalysis(trend)));
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "30D"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trendId").value(101))
                .andExpect(jsonPath("$.data.mentionCount").value(nullValue()))
                .andExpect(jsonPath("$.data.analysisWindow").value(nullValue()))
                .andExpect(jsonPath("$.data.evidence").value(nullValue()))
                .andExpect(jsonPath("$.data.aiAnalysis.status").value("COMPLETED"));
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"24H", "7D", "30D"})
    @DisplayName("세 가지 기간 값만 허용한다")
    void acceptsAllowedPeriods(String period) throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", period))
                .andExpect(status().isOk());
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"24h", "1D", "7", "30d", ""})
    @DisplayName("잘못된 기간 값은 서비스를 호출하지 않고 400을 반환한다")
    void rejectsInvalidPeriod(String period) throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", period))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("기간이 누락되면 서비스를 호출하지 않고 400을 반환한다")
    void rejectsMissingPeriod() throws Exception {
        mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."))
                .andDo(document("trends-detail-invalid-period", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("존재하지 않는 트렌드는 404를 반환한다")
    void returnsNotFound() throws Exception {
        given(trendService.getTrendDetail(999L, AnalysisPeriod.HOURS_24))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));
        mockMvc.perform(get("/trends/{trendId}", 999L).queryParam("period", "24H"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 트렌드입니다."))
                .andDo(document("trends-detail-not-found", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"0", "-1", "abc", "9223372036854775808"})
    @DisplayName("잘못된 트렌드 ID는 서비스를 호출하지 않고 400을 반환한다")
    void rejectsInvalidId(String trendId) throws Exception {
        mockMvc.perform(get("/trends/{trendId}", trendId).queryParam("period", "24H"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andDo(document("trends-detail-invalid-id", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("인증 없이 요청하면 401을 반환하고 트렌드 서비스를 호출하지 않는다")
    void existingSecurityBlocksAnonymousRequest() throws Exception {
        // given & when & then
        mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
        then(trendService).shouldHaveNoInteractions();
    }
}
