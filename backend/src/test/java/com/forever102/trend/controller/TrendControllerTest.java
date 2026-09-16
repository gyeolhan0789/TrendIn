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
import com.forever102.member.domain.Domain;
import com.forever102.trend.TrendFixture;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.dto.TrendContentResponse;
import com.forever102.trend.dto.TrendContentResponse.ContentItemResponse;
import com.forever102.trend.dto.TrendDetailResponse;
import com.forever102.trend.dto.TrendHistoryResponse;
import com.forever102.trend.dto.TrendHistoryResponse.HistoryPointResponse;
import com.forever102.trend.dto.TrendListResponse;
import com.forever102.trend.dto.TrendRelatedKeywordResponse;
import com.forever102.trend.dto.TrendRelatedKeywordResponse.RelatedKeywordResponse;
import com.forever102.trend.service.TrendHistoryService;
import com.forever102.trend.service.TrendRegionService;
import com.forever102.trend.service.TrendRegionHistoryService;
import com.forever102.trend.service.TrendService;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
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
    @MockitoBean TrendRegionService trendRegionService;
    @MockitoBean TrendRegionHistoryService trendRegionHistoryService;

    @Test
    @WithMockUser
    @DisplayName("최신 명세의 분야별 트렌드 목록을 반환하고 문서화한다")
    void returnsTrendList() throws Exception {
        // given
        var trend = TrendFixture.trend();
        var metric = TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123);
        var result = new PageImpl<>(List.of(metric),
                PageRequest.of(0, 5), 1);
        given(trendService.getTrends(
                Domain.FASHION, TrendType.RISING, AnalysisPeriod.DAYS_7, 0, 5))
                .willReturn(TrendListResponse.from(result, Map.of(81L, trend),
                        TrendFixture.window(AnalysisPeriod.DAYS_7)));

        // when & then
        mockMvc.perform(get("/trends")
                        .queryParam("domain", "FASHION")
                        .queryParam("type", "RISING")
                        .queryParam("period", "7D")
                        .queryParam("page", "0")
                        .queryParam("size", "5")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content[0].trendId").value(101))
                .andExpect(jsonPath("$.data.content[0].keywordId").value(81))
                .andExpect(jsonPath("$.data.content[0].domain.domain").value("FASHION"))
                .andExpect(jsonPath("$.data.content[0].trendTypes[0]").value("RISING"))
                .andExpect(jsonPath("$.data.content[0].rank").value(1))
                .andExpect(jsonPath("$.data.content[0].growthRate").value(249.6))
                .andExpect(jsonPath("$.data.page").value(0))
                .andExpect(jsonPath("$.data.size").value(5))
                .andExpect(jsonPath("$.data.hasNext").value(false))
                .andExpect(jsonPath("$.data.analysisWindow.recentStart")
                        .value("2026-08-24T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.content[0].firstDetectedAt").doesNotExist())
                .andDo(document("trends-list", preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        queryParameters(
                                parameterWithName("domain").description("필수 분야: DEVELOP, FASHION"),
                                parameterWithName("type").description("필수 유형: CURRENT, NEW, RISING"),
                                parameterWithName("period").description("필수 조회 기간: 24H, 7D, 30D"),
                                parameterWithName("page").optional().description("페이지 번호. 기본 0"),
                                parameterWithName("size").optional().description("페이지 크기. 기본 20")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.content").type(JsonFieldType.ARRAY).description("트렌드 목록"),
                                fieldWithPath("data.content[].trendId").type(JsonFieldType.NUMBER).description("트렌드 ID"),
                                fieldWithPath("data.content[].keywordId").type(JsonFieldType.NUMBER).description("키워드 ID"),
                                fieldWithPath("data.content[].keyword").type(JsonFieldType.STRING).description("키워드"),
                                fieldWithPath("data.content[].description").type(JsonFieldType.STRING).description("짧은 설명"),
                                fieldWithPath("data.content[].domain.domain").type(JsonFieldType.STRING).description("분야 값"),
                                fieldWithPath("data.content[].domain.name").type(JsonFieldType.STRING).description("분야 이름"),
                                fieldWithPath("data.content[].trendTypes").type(JsonFieldType.ARRAY).description("트렌드 유형 목록"),
                                fieldWithPath("data.content[].rank").type(JsonFieldType.NUMBER).description("언급량 순위"),
                                fieldWithPath("data.content[].mentionCount").type(JsonFieldType.NUMBER).description("언급량"),
                                fieldWithPath("data.content[].previousMentionCount").type(JsonFieldType.NUMBER).description("직전 언급량"),
                                fieldWithPath("data.content[].growthAmount").type(JsonFieldType.NUMBER).description("언급 증가량"),
                                fieldWithPath("data.content[].growthRate").type(JsonFieldType.NUMBER).optional().description("언급 증가율"),
                                fieldWithPath("data.page").type(JsonFieldType.NUMBER).description("현재 페이지"),
                                fieldWithPath("data.size").type(JsonFieldType.NUMBER).description("페이지 크기"),
                                fieldWithPath("data.hasNext").type(JsonFieldType.BOOLEAN).description("다음 페이지 여부"),
                                fieldWithPath("data.analysisWindow.recentStart").type(JsonFieldType.STRING).description("현재 구간 시작"),
                                fieldWithPath("data.analysisWindow.recentEnd").type(JsonFieldType.STRING).description("현재 구간 종료"),
                                fieldWithPath("data.analysisWindow.previousStart").type(JsonFieldType.STRING).description("이전 구간 시작"),
                                fieldWithPath("data.analysisWindow.previousEnd").type(JsonFieldType.STRING).description("이전 구간 종료"))));
    }

    @Test
    @WithMockUser
    @DisplayName("목록 조회의 page와 size를 생략하면 기본값을 사용한다")
    void usesDefaultPagination() throws Exception {
        // when
        mockMvc.perform(get("/trends").queryParam("domain", "DEVELOP")
                        .queryParam("type", "CURRENT").queryParam("period", "24H"))
                .andExpect(status().isOk());

        // then
        then(trendService).should().getTrends(
                Domain.DEVELOP, TrendType.CURRENT, AnalysisPeriod.HOURS_24, 0, 20);
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"domain", "type", "period"})
    @DisplayName("목록 조회 필수 파라미터가 누락되면 400을 반환한다")
    void rejectsMissingListParameter(String omitted) throws Exception {
        // given
        var request = get("/trends");
        if (!omitted.equals("domain")) request.queryParam("domain", "FASHION");
        if (!omitted.equals("type")) request.queryParam("type", "CURRENT");
        if (!omitted.equals("period")) request.queryParam("period", "7D");

        // when & then
        mockMvc.perform(request).andExpect(status().isBadRequest());
        then(trendService).shouldHaveNoInteractions();
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"domain=BEAUTY", "type=POPULAR", "period=1D", "page=-1", "size=0"})
    @DisplayName("목록 조회 파라미터가 잘못되면 400을 반환한다")
    void rejectsInvalidListParameter(String invalid) throws Exception {
        // given
        String[] pair = invalid.split("=");
        var request = get("/trends")
                .queryParam("domain", pair[0].equals("domain") ? pair[1] : "FASHION")
                .queryParam("type", pair[0].equals("type") ? pair[1] : "CURRENT")
                .queryParam("period", pair[0].equals("period") ? pair[1] : "7D")
                .queryParam("page", pair[0].equals("page") ? pair[1] : "0")
                .queryParam("size", pair[0].equals("size") ? pair[1] : "20");

        // when & then
        mockMvc.perform(request).andExpect(status().isBadRequest());
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @DisplayName("인증 없이 목록을 요청하면 401을 반환한다")
    void blocksAnonymousTrendList() throws Exception {
        // when & then
        mockMvc.perform(get("/trends").queryParam("domain", "FASHION")
                        .queryParam("type", "CURRENT").queryParam("period", "7D"))
                .andExpect(status().isUnauthorized());
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("최신 명세의 트렌드 상세 응답을 반환하고 문서화한다")
    void returnsTrendDetail() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_7))
                .willReturn(TrendDetailResponse.from(trend,
                        TrendFixture.metric(trend, AnalysisPeriod.DAYS_7, 430, 123), AnalysisPeriod.DAYS_7));

        // when & then
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
    @DisplayName("요청 기간 지표가 없으면 지표 필드는 null이고 트렌드 유형은 비운다")
    void returnsNullMetricFields() throws Exception {
        // given
        var trend = TrendFixture.trend();
        given(trendService.getTrendDetail(101L, AnalysisPeriod.DAYS_30))
                .willReturn(TrendDetailResponse.from(trend, null, AnalysisPeriod.DAYS_30));

        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "30D"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trendTypes").isEmpty())
                .andExpect(jsonPath("$.data.mentionCount").value(nullValue()))
                .andExpect(jsonPath("$.data.analysisWindow").value(nullValue()))
                .andExpect(jsonPath("$.data.summary").isString());
    }

    @Test
    @WithMockUser
    @DisplayName("기간별 관심도 시계열을 bucketStart와 bucketEnd로 반환하고 문서화한다")
    void returnsTrendHistory() throws Exception {
        // given
        var start = OffsetDateTime.parse("2026-08-01T00:00:00+09:00");
        var end = OffsetDateTime.parse("2026-08-31T00:00:00+09:00");
        given(trendHistoryService.getHistory(101L, AnalysisPeriod.DAYS_30))
                .willReturn(TrendHistoryResponse.of(101L, AnalysisPeriod.DAYS_30, start, end,
                        List.of(new HistoryPointResponse(start, start.plusDays(3), 120L),
                                new HistoryPointResponse(start.plusDays(3), start.plusDays(6), 145L))));

        // when & then
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

    @Test
    @WithMockUser
    @DisplayName("트렌드 키워드의 관련 콘텐츠를 반환하고 문서화한다")
    void returnsTrendContents() throws Exception {
        // given
        var publishedAt = OffsetDateTime.parse("2026-08-30T10:00:00+09:00");
        given(trendService.getTrendContents(101L, 0, 5))
                .willReturn(new TrendContentResponse(List.of(
                        new ContentItemResponse(301L, "발레코어 스니커즈가 뜬다", "Vogue Korea",
                                "https://example.com/articles/301", publishedAt)),
                        0, 5, false));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/contents", 101L)
                        .queryParam("page", "0")
                        .queryParam("size", "5")
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content[0].contentId").value(301))
                .andExpect(jsonPath("$.data.content[0].title").value("발레코어 스니커즈가 뜬다"))
                .andExpect(jsonPath("$.data.content[0].source").value("Vogue Korea"))
                .andExpect(jsonPath("$.data.content[0].url").value("https://example.com/articles/301"))
                .andExpect(jsonPath("$.data.content[0].publishedAt")
                        .value("2026-08-30T10:00:00+09:00"))
                .andExpect(jsonPath("$.data.hasNext").value(false))
                .andDo(document("trends-contents",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId").description("조회할 트렌드 ID. 양의 정수")),
                        queryParameters(
                                parameterWithName("page").optional().description("페이지 번호. 기본 0"),
                                parameterWithName("size").optional().description("페이지 크기. 기본 10")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL).description("성공 시 null"),
                                fieldWithPath("data.content").type(JsonFieldType.ARRAY).description("관련 콘텐츠 목록"),
                                fieldWithPath("data.content[].contentId").type(JsonFieldType.NUMBER).description("콘텐츠 ID"),
                                fieldWithPath("data.content[].title").type(JsonFieldType.STRING).description("콘텐츠 제목"),
                                fieldWithPath("data.content[].source").type(JsonFieldType.STRING).description("콘텐츠 출처"),
                                fieldWithPath("data.content[].url").type(JsonFieldType.STRING).description("원문 URL"),
                                fieldWithPath("data.content[].publishedAt").type(JsonFieldType.STRING).description("게시 시각"),
                                fieldWithPath("data.page").type(JsonFieldType.NUMBER).description("현재 페이지"),
                                fieldWithPath("data.size").type(JsonFieldType.NUMBER).description("페이지 크기"),
                                fieldWithPath("data.hasNext").type(JsonFieldType.BOOLEAN).description("다음 페이지 여부"))));
    }

    @Test
    @WithMockUser
    @DisplayName("관련 콘텐츠가 없으면 빈 목록을 반환한다")
    void returnsEmptyTrendContents() throws Exception {
        // given
        given(trendService.getTrendContents(101L, 0, 10))
                .willReturn(new TrendContentResponse(List.of(), 0, 10, false));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/contents", 101L))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content").isEmpty())
                .andExpect(jsonPath("$.data.page").value(0))
                .andExpect(jsonPath("$.data.size").value(10))
                .andExpect(jsonPath("$.data.totalElements").doesNotExist())
                .andExpect(jsonPath("$.data.totalPages").doesNotExist());
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"page=-1", "size=0"})
    @DisplayName("관련 콘텐츠 페이지 파라미터가 잘못되면 400을 반환한다")
    void rejectsInvalidContentPagination(String invalid) throws Exception {
        // given
        String[] pair = invalid.split("=");

        // when & then
        mockMvc.perform(get("/trends/{trendId}/contents", 101L)
                        .queryParam(pair[0], pair[1]))
                .andExpect(status().isBadRequest());
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("존재하지 않는 트렌드의 관련 콘텐츠 요청은 404를 반환한다")
    void returnsNotFoundForTrendContents() throws Exception {
        // given
        given(trendService.getTrendContents(999L, 0, 10))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/contents", 999L))
                .andExpect(status().isNotFound());
    }

    @Test
    @WithMockUser
    @DisplayName("트렌드의 연관 키워드를 관계 점수순으로 반환하고 문서화한다")
    void returnsRelatedKeywords() throws Exception {
        // given
        given(trendService.getRelatedKeywords(101L))
                .willReturn(new TrendRelatedKeywordResponse(101L, List.of(
                        new RelatedKeywordResponse(
                                82L, "Mary Jane Sneakers", new BigDecimal("87.50")),
                        new RelatedKeywordResponse(
                                83L, "Retro Sneakers", new BigDecimal("72.00")))));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/related-keywords", 101L)
                        .header("Authorization", "Bearer example-token"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trendId").value(101))
                .andExpect(jsonPath("$.data.relatedKeywords[0].keywordId").value(82))
                .andExpect(jsonPath("$.data.relatedKeywords[0].keyword")
                        .value("Mary Jane Sneakers"))
                .andExpect(jsonPath("$.data.relatedKeywords[0].relationScore").value(87.5))
                .andExpect(jsonPath("$.data.relatedKeywords[0].previousRelationScore")
                        .doesNotExist())
                .andExpect(jsonPath("$.data.relatedKeywords[0].growthRate").doesNotExist())
                .andExpect(jsonPath("$.data.relatedKeywords[0].relationStatus").doesNotExist())
                .andDo(document("trends-related-keywords",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName("Authorization").description("인증 토큰")),
                        pathParameters(parameterWithName("trendId")
                                .description("조회할 트렌드 ID. 양의 정수")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 시 null"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER)
                                        .description("트렌드 ID"),
                                fieldWithPath("data.relatedKeywords").type(JsonFieldType.ARRAY)
                                        .description("연관 키워드 목록"),
                                fieldWithPath("data.relatedKeywords[].keywordId")
                                        .type(JsonFieldType.NUMBER).description("연관 키워드 ID"),
                                fieldWithPath("data.relatedKeywords[].keyword")
                                        .type(JsonFieldType.STRING).description("연관 키워드"),
                                fieldWithPath("data.relatedKeywords[].relationScore")
                                        .type(JsonFieldType.NUMBER)
                                        .description("0~100 범위의 관계 점수. 소수 둘째 자리까지 사용"))));
    }

    @Test
    @WithMockUser
    @DisplayName("연관 키워드가 없으면 빈 목록을 반환한다")
    void returnsEmptyRelatedKeywords() throws Exception {
        // given
        given(trendService.getRelatedKeywords(101L))
                .willReturn(new TrendRelatedKeywordResponse(101L, List.of()));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/related-keywords", 101L))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.trendId").value(101))
                .andExpect(jsonPath("$.data.relatedKeywords").isEmpty());
    }

    @Test
    @WithMockUser
    @DisplayName("존재하지 않는 트렌드의 연관 키워드 요청은 404를 반환한다")
    void returnsNotFoundForRelatedKeywords() throws Exception {
        // given
        given(trendService.getRelatedKeywords(999L))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));

        // when & then
        mockMvc.perform(get("/trends/{trendId}/related-keywords", 999L))
                .andExpect(status().isNotFound());
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"24H", "7D", "30D"})
    @DisplayName("허용된 기간 값으로 상세 조회를 요청하면 200을 반환한다")
    void acceptsAllowedPeriods(String period) throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", period))
                .andExpect(status().isOk());
    }

    @Test
    @WithMockUser
    @DisplayName("상세 조회의 기간이 누락되면 400을 반환한다")
    void rejectsMissingDetailPeriod() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L))
                .andExpect(status().isBadRequest())
                .andDo(document("trends-detail-invalid-period", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
        then(trendService).shouldHaveNoInteractions();
    }

    @Test
    @WithMockUser
    @DisplayName("시계열 조회의 기간이 누락되면 400을 반환한다")
    void rejectsMissingHistoryPeriod() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}/history", 101L))
                .andExpect(status().isBadRequest());
        then(trendHistoryService).shouldHaveNoInteractions();
    }

    @ParameterizedTest
    @WithMockUser
    @ValueSource(strings = {"0", "-1", "abc", "9223372036854775808"})
    @DisplayName("유효하지 않은 트렌드 ID로 상세 조회를 요청하면 400을 반환한다")
    void rejectsInvalidTrendId(String trendId) throws Exception {
        // when & then
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
    @DisplayName("존재하지 않는 트렌드의 상세 조회는 404를 반환한다")
    void returnsNotFound() throws Exception {
        // given
        given(trendService.getTrendDetail(999L, AnalysisPeriod.HOURS_24))
                .willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND));

        // when & then
        mockMvc.perform(get("/trends/{trendId}", 999L).queryParam("period", "24H"))
                .andExpect(status().isNotFound())
                .andDo(document("trends-detail-not-found", preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("false"),
                                fieldWithPath("message").type(JsonFieldType.STRING).description("오류 메시지"))));
    }

    @Test
    @DisplayName("인증 없이 트렌드 상세를 요청하면 401을 반환한다")
    void blocksAnonymousTrendDetail() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}", 101L).queryParam("period", "24H"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("인증 없이 시계열을 요청하면 401을 반환한다")
    void blocksAnonymousTrendHistory() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}/history", 101L).queryParam("period", "24H"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("인증 없이 관련 콘텐츠를 요청하면 401을 반환한다")
    void blocksAnonymousTrendContents() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}/contents", 101L))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("인증 없이 연관 키워드를 요청하면 401을 반환한다")
    void blocksAnonymousRelatedKeywords() throws Exception {
        // when & then
        mockMvc.perform(get("/trends/{trendId}/related-keywords", 101L))
                .andExpect(status().isUnauthorized());
    }
}
