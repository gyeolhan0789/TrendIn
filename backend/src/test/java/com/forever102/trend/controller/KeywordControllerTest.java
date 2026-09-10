package com.forever102.trend.controller;

import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.never;
import static org.springframework.restdocs.headers.HeaderDocumentation.headerWithName;
import static org.springframework.restdocs.headers.HeaderDocumentation.requestHeaders;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessRequest;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.restdocs.request.RequestDocumentation.parameterWithName;
import static org.springframework.restdocs.request.RequestDocumentation.queryParameters;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.global.config.SecurityTestConfig;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.TrendType;
import com.forever102.trend.dto.KeywordSearchResponse;
import com.forever102.trend.dto.KeywordSearchResponse.DomainResponse;
import com.forever102.trend.dto.KeywordSearchResponse.KeywordSearchItemResponse;
import com.forever102.trend.service.KeywordService;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(KeywordController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class KeywordControllerTest {

    @Autowired MockMvc mockMvc;
    @Autowired JwtTokenProvider jwtTokenProvider;
    @MockitoBean KeywordService keywordService;

    @Test
    @DisplayName("키워드를 검색하면 트렌드 정보를 포함한 페이지를 반환하고 문서화한다")
    void searchesKeywords() throws Exception {
        // given
        var item = new KeywordSearchItemResponse(50L, "AI Agent",
                new DomainResponse(Domain.DEVELOP, "개발"), 32L,
                List.of(TrendType.CURRENT), new BigDecimal("32.4"));
        given(keywordService.search("ai", Domain.DEVELOP, 0, 20))
                .willReturn(new KeywordSearchResponse(List.of(item), 0, 20, false));

        // when & then
        mockMvc.perform(get("/keywords/search")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("query", "ai")
                        .queryParam("domain", "DEVELOP")
                        .queryParam("page", "0")
                        .queryParam("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content[0].keywordId").value(50))
                .andExpect(jsonPath("$.data.content[0].keyword").value("AI Agent"))
                .andExpect(jsonPath("$.data.content[0].domain.code").value("DEVELOP"))
                .andExpect(jsonPath("$.data.content[0].trendId").value(32))
                .andExpect(jsonPath("$.data.content[0].trendTypes[0]").value("CURRENT"))
                .andExpect(jsonPath("$.data.content[0].growthRate").value(32.4))
                .andDo(document("keywords-search",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        queryParameters(
                                parameterWithName("query").description("검색할 키워드명"),
                                parameterWithName("domain").optional()
                                        .description("선택 분야: DEVELOP, FASHION"),
                                parameterWithName("page").optional().description("페이지 번호, 기본값 0"),
                                parameterWithName("size").optional().description("페이지 크기, 기본값 20")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data.content[].keywordId").type(JsonFieldType.NUMBER)
                                        .description("관심 키워드 등록에 사용할 키워드 ID"),
                                fieldWithPath("data.content[].keyword").type(JsonFieldType.STRING).description("키워드명"),
                                fieldWithPath("data.content[].domain.code").type(JsonFieldType.STRING).description("분야 코드"),
                                fieldWithPath("data.content[].domain.name").type(JsonFieldType.STRING).description("분야 이름"),
                                fieldWithPath("data.content[].trendId").type(JsonFieldType.NUMBER).optional()
                                        .description("현재 트렌드 ID, 트렌드가 아니면 null"),
                                fieldWithPath("data.content[].trendTypes").type(JsonFieldType.ARRAY)
                                        .description("현재 트렌드 유형, 트렌드가 아니면 빈 배열"),
                                fieldWithPath("data.content[].growthRate").type(JsonFieldType.NUMBER).optional()
                                        .description("완료된 24H 지표 증가율, 값이 없으면 null"),
                                fieldWithPath("data.page").type(JsonFieldType.NUMBER).description("현재 페이지"),
                                fieldWithPath("data.size").type(JsonFieldType.NUMBER).description("페이지 크기"),
                                fieldWithPath("data.hasNext").type(JsonFieldType.BOOLEAN).description("다음 페이지 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("검색 결과가 없으면 빈 content를 반환한다")
    void returnsEmptyContent() throws Exception {
        // given
        given(keywordService.search("unknown", null, 0, 20))
                .willReturn(new KeywordSearchResponse(List.of(), 0, 20, false));

        // when & then
        mockMvc.perform(get("/keywords/search")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("query", "unknown"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content").isEmpty());
    }

    @Test
    @DisplayName("검색어가 누락되면 400으로 응답한다")
    void rejectsMissingQuery() throws Exception {
        // when
        mockMvc.perform(get("/keywords/search")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isBadRequest());

        // then
        then(keywordService).should(never()).search(
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.anyInt(), org.mockito.ArgumentMatchers.anyInt());
    }

    @Test
    @DisplayName("지원하지 않는 분야는 400으로 응답한다")
    void rejectsInvalidDomain() throws Exception {
        // when
        mockMvc.perform(get("/keywords/search")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("query", "spring")
                        .queryParam("domain", "DESIGN"))
                .andExpect(status().isBadRequest());

        // then
        then(keywordService).shouldHaveNoInteractions();
    }

    private String bearerToken() {
        return "Bearer " + jwtTokenProvider.issue(1L).accessToken();
    }
}
