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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.backend.global.config.SecurityConfig;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import com.forever102.backend.trend.TrendFixture;
import com.forever102.backend.trend.dto.TrendDetailResponse;
import com.forever102.backend.trend.service.TrendService;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.restdocs.payload.FieldDescriptor;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(TrendController.class)
@Import(SecurityConfig.class)
@AutoConfigureRestDocs
class TrendControllerTest {

    @Autowired
    private MockMvc mockMvc;
    @MockitoBean
    private TrendService trendService;

    @Test
    @WithMockUser
    @DisplayName("기간 파라미터 없이 24H 상세 결과를 조회하고 문서화한다")
    void returnsDetailWithoutPeriod() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L)).willReturn(TrendDetailResponse.from(trend,
                TrendFixture.analysis(trend, 430, 123)));
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value(nullValue()))
                .andExpect(jsonPath("$.data.domain.code").value("FASHION"))
                .andExpect(jsonPath("$.data.domain.name").value("패션"))
                .andExpect(jsonPath("$.data.domain.domainId").doesNotExist())
                .andExpect(jsonPath("$.data.category").doesNotExist())
                .andExpect(jsonPath("$.data.mentionCount").value(430))
                .andExpect(jsonPath("$.data.previousMentionCount").value(123))
                .andExpect(jsonPath("$.data.growthAmount").value(307))
                .andExpect(jsonPath("$.data.growthRate").value(249.6))
                .andExpect(jsonPath("$.data.aiAnalysis.sourceContentIds[0]").value(301))
                .andDo(document("trends-detail", preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰. 인증 처리는 공통 인증 계층에서 담당한다.")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수.")),
                        responseFields(detailFields())));
    }

    @Test
    @WithMockUser
    @DisplayName("24H 분석이 없으면 200과 기본 정보 및 명시적 null 필드를 반환한다")
    void returnsNullAnalysisWithOk() throws Exception {
        // given
        given(trendService.getTrendDetail(101L)).willReturn(TrendDetailResponse.from(TrendFixture.trend(), null));
        var fields = new ArrayList<>(baseFields());
        for (String field : List.of("trendType", "mentionCount", "previousMentionCount", "growthAmount",
                "growthRate", "analysisWindow", "analyzedAt", "evidence", "aiAnalysis")) {
            fields.add(fieldWithPath("data." + field).type(JsonFieldType.NULL).description("24H 분석 데이터가 없어 null"));
        }
        // when & then
        var result = mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isOk()).andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.trendId").value(101))
                .andExpect(jsonPath("$.data.description").isString());
        for (String field : List.of("trendType", "mentionCount", "previousMentionCount", "growthAmount",
                "growthRate", "analysisWindow", "analyzedAt", "evidence", "aiAnalysis")) {
            result.andExpect(jsonPath("$.data." + field).value(nullValue()));
        }
        result.andDo(document("trends-detail-no-analysis", preprocessResponse(prettyPrint()), responseFields(fields)));
    }

    @Test
    @WithMockUser
    @DisplayName("이전 언급량이 0이면 응답 JSON에서 증가율이 null이다")
    void returnsNullGrowthRate() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L)).willReturn(TrendDetailResponse.from(trend,
                TrendFixture.analysis(trend, 430, 0)));
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.previousMentionCount").value(0))
                .andExpect(jsonPath("$.data.growthAmount").value(430))
                .andExpect(jsonPath("$.data.growthRate").value(nullValue()));
    }

    @Test
    @WithMockUser
    @DisplayName("존재하지 않는 트렌드는 공통 오류 구조로 404를 반환한다")
    void returnsNotFound() throws Exception {
        // given
        given(trendService.getTrendDetail(999L)).willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 999L))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("존재하지 않는 트렌드입니다."))
                .andDo(document("trends-detail-not-found", preprocessResponse(prettyPrint()), responseFields(errorFields())));
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"0", "-1", "abc", "9223372036854775808"})
    @DisplayName("잘못된 트렌드 ID는 서비스를 호출하지 않고 400으로 응답한다")
    void rejectsInvalidId(String id) throws Exception {
        // given & when & then
        mockMvc.perform(get("/trends/{trendId}", id))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andDo(document("trends-detail-invalid-id", preprocessResponse(prettyPrint()), responseFields(errorFields())));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("현재 공통 보안 설정은 비인증 요청을 차단하며 트렌드 서비스를 호출하지 않는다")
    void existingSecurityBlocksAnonymousRequest() throws Exception {
        // given & when & then
        mockMvc.perform(get("/trends/{trendId}", 101L)).andExpect(status().isForbidden());
        then(trendService).shouldHaveNoInteractions();
    }

    private List<FieldDescriptor> baseFields() {
        return List.of(
                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                fieldWithPath("data.keywordId").type(JsonFieldType.NUMBER).description("키워드 ID"),
                fieldWithPath("data.keyword").type(JsonFieldType.STRING).description("키워드"),
                fieldWithPath("data.description").type(JsonFieldType.STRING).optional().description("짧은 한 줄 설명. AI 요약과 별개. 미등록 시 null"),
                fieldWithPath("data.firstDetectedAt").type(JsonFieldType.STRING).description("최초 탐지 시각. 오프셋 포함 ISO 8601"),
                fieldWithPath("data.domain.code").type(JsonFieldType.STRING).description("분야 코드: DEVELOP, FASHION"),
                fieldWithPath("data.domain.name").type(JsonFieldType.STRING).description("분야 표시명: 개발, 패션"));
    }

    private List<FieldDescriptor> detailFields() {
        var fields = new ArrayList<>(baseFields());
        fields.addAll(List.of(
                fieldWithPath("data.trendType").type(JsonFieldType.STRING).optional().description("분석에 저장된 트렌드 유형"),
                fieldWithPath("data.mentionCount").type(JsonFieldType.NUMBER).optional().description("최근 24H 언급량"),
                fieldWithPath("data.previousMentionCount").type(JsonFieldType.NUMBER).optional().description("직전 24H 언급량"),
                fieldWithPath("data.growthAmount").type(JsonFieldType.NUMBER).optional().description("최근 언급량 - 직전 언급량"),
                fieldWithPath("data.growthRate").type(JsonFieldType.NUMBER).optional().description("증가율(%). 소수 첫째 자리 반올림. 직전 언급량이 0이면 null"),
                fieldWithPath("data.analysisWindow").type(JsonFieldType.OBJECT).optional().description("실제로 분석한 연속 24H 구간. 시작 포함, 종료 제외"),
                fieldWithPath("data.analysisWindow.recentStart").type(JsonFieldType.STRING).description("최근 구간 시작"),
                fieldWithPath("data.analysisWindow.recentEnd").type(JsonFieldType.STRING).description("최근 구간 종료"),
                fieldWithPath("data.analysisWindow.previousStart").type(JsonFieldType.STRING).description("직전 구간 시작"),
                fieldWithPath("data.analysisWindow.previousEnd").type(JsonFieldType.STRING).description("직전 구간 종료"),
                fieldWithPath("data.analyzedAt").type(JsonFieldType.STRING).optional().description("저장된 분석 시각"),
                fieldWithPath("data.evidence").type(JsonFieldType.OBJECT).optional().description("해당 분석의 판정 근거. 없으면 null"),
                fieldWithPath("data.evidence.ruleVersion").type(JsonFieldType.STRING).optional().description("적용한 규칙 버전"),
                fieldWithPath("data.evidence.ruleDescription").type(JsonFieldType.STRING).optional().description("적용한 규칙 설명"),
                fieldWithPath("data.evidence.appliedThresholds").type(JsonFieldType.OBJECT).optional().description("분석에서 사용한 숫자 임계값. 키는 적용 규칙에 따라 달라짐"),
                fieldWithPath("data.evidence.appliedThresholds.*").type(JsonFieldType.NUMBER).description("저장된 임계값"),
                fieldWithPath("data.evidence.dataCoverage").type(JsonFieldType.STRING).optional().description("저장된 데이터 완전성 상태"),
                fieldWithPath("data.aiAnalysis").type(JsonFieldType.OBJECT).optional().description("해당 분석의 AI 결과. 없으면 null"),
                fieldWithPath("data.aiAnalysis.status").type(JsonFieldType.STRING).description("저장된 AI 분석 상태"),
                fieldWithPath("data.aiAnalysis.summary").type(JsonFieldType.STRING).optional().description("관련 콘텐츠를 기반으로 생성한 요약"),
                fieldWithPath("data.aiAnalysis.reason").type(JsonFieldType.STRING).optional().description("AI 분석 이유"),
                fieldWithPath("data.aiAnalysis.sourceContentIds").type(JsonFieldType.ARRAY).description("실제로 AI 분석에 사용한 콘텐츠 ID"),
                fieldWithPath("data.aiAnalysis.generatedAt").type(JsonFieldType.STRING).optional().description("AI 생성 시각")));
        return fields;
    }

    private List<FieldDescriptor> errorFields() {
        return List.of(fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"));
    }
}
