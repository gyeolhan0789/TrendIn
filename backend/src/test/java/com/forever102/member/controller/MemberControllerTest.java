package com.forever102.member.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.springframework.restdocs.headers.HeaderDocumentation.headerWithName;
import static org.springframework.restdocs.headers.HeaderDocumentation.requestHeaders;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessRequest;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.requestFields;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.restdocs.request.RequestDocumentation.parameterWithName;
import static org.springframework.restdocs.request.RequestDocumentation.pathParameters;
import static org.springframework.restdocs.request.RequestDocumentation.queryParameters;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.global.config.SecurityTestConfig;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.dto.InterestKeywordResponse;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.member.dto.RecommendedKeywordResponse;
import com.forever102.member.dto.RecommendedKeywordResponse.DomainResponse;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.dto.SavedTrendListResponse.SavedTrendResponse;
import com.forever102.member.service.MemberInterestKeywordService;
import com.forever102.member.service.MemberService;
import com.forever102.member.service.SavedTrendService;
import com.forever102.member.domain.Domain;
import com.forever102.trend.domain.AnalysisPeriod;
import com.forever102.trend.domain.TrendType;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(MemberController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class MemberControllerTest {

    private static final String URL = "/members/me/interest-keywords";
    private static final String ME_URL = "/members/me";
    private static final String VALID_UPDATE_REQUEST = "{\"nickname\":\"newNickname\"}";
    private static final String SHORT_NICKNAME_REQUEST = "{\"nickname\":\"  a  \"}";
    private static final Long MEMBER_ID = 1L;
    private static final Long KEYWORD_ID = 81L;

    @Autowired MockMvc mockMvc;
    @Autowired JwtTokenProvider jwtTokenProvider;
    @MockitoBean MemberInterestKeywordService interestKeywordService;
    @MockitoBean MemberService memberService;
    @MockitoBean SavedTrendService savedTrendService;

    @Test
    @DisplayName("저장한 트렌드를 선택한 기간과 최신 저장순 페이지로 조회하고 문서화한다")
    void getsSavedTrends() throws Exception {
        // given
        OffsetDateTime savedAt = OffsetDateTime.parse("2026-08-31T09:00:00+09:00");
        SavedTrendListResponse response = new SavedTrendListResponse(List.of(
                new SavedTrendResponse(15L, 101L, 81L, "Ballet Sneakers",
                        new SavedTrendListResponse.DomainResponse(Domain.FASHION, "패션"),
                        List.of(TrendType.RISING),
                        "발레 슈즈 디자인을 접목한 스니커즈가 주목받고 있습니다.",
                        430L, new BigDecimal("249.6"), savedAt)),
                0, 20, false);
        given(savedTrendService.getSavedTrends(MEMBER_ID, AnalysisPeriod.DAYS_7, 0, 20))
                .willReturn(response);

        // when & then
        mockMvc.perform(get("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("period", "7D")
                        .queryParam("page", "0")
                        .queryParam("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.content[0].savedTrendId").value(15))
                .andExpect(jsonPath("$.data.content[0].trendId").value(101))
                .andExpect(jsonPath("$.data.content[0].keywordId").value(81))
                .andExpect(jsonPath("$.data.content[0].keyword").value("Ballet Sneakers"))
                .andExpect(jsonPath("$.data.content[0].domain.code").value("FASHION"))
                .andExpect(jsonPath("$.data.content[0].domain.name").value("패션"))
                .andExpect(jsonPath("$.data.content[0].trendTypes[0]").value("RISING"))
                .andExpect(jsonPath("$.data.content[0].mentionCount").value(430))
                .andExpect(jsonPath("$.data.content[0].growthRate").value(249.6))
                .andExpect(jsonPath("$.data.content[0].savedAt")
                        .value("2026-08-31T09:00:00+09:00"))
                .andExpect(jsonPath("$.data.page").value(0))
                .andExpect(jsonPath("$.data.size").value(20))
                .andExpect(jsonPath("$.data.hasNext").value(false))
                .andDo(document("members-saved-trends",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        queryParameters(
                                parameterWithName("period").optional()
                                        .description("지표 기간: 24H, 7D, 30D. 기본값 24H"),
                                parameterWithName("page").optional()
                                        .description("페이지 번호. 0부터 시작하며 기본값 0"),
                                parameterWithName("size").optional()
                                        .description("페이지 크기. 기본값 20")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data.content[].savedTrendId").type(JsonFieldType.NUMBER)
                                        .description("저장 트렌드 ID"),
                                fieldWithPath("data.content[].trendId").type(JsonFieldType.NUMBER)
                                        .description("트렌드 ID"),
                                fieldWithPath("data.content[].keywordId").type(JsonFieldType.NUMBER)
                                        .description("키워드 ID"),
                                fieldWithPath("data.content[].keyword").type(JsonFieldType.STRING)
                                        .description("키워드 이름"),
                                fieldWithPath("data.content[].domain.code").type(JsonFieldType.STRING)
                                        .description("분야 코드"),
                                fieldWithPath("data.content[].domain.name").type(JsonFieldType.STRING)
                                        .description("분야 이름"),
                                fieldWithPath("data.content[].trendTypes").type(JsonFieldType.ARRAY)
                                        .description("현재 트렌드 유형. 현재 유형이 없으면 빈 배열"),
                                fieldWithPath("data.content[].description").type(JsonFieldType.STRING)
                                        .description("트렌드 설명"),
                                fieldWithPath("data.content[].mentionCount").type(JsonFieldType.NUMBER)
                                        .optional().description("선택 기간 언급량. 지표가 없으면 null"),
                                fieldWithPath("data.content[].growthRate").type(JsonFieldType.NUMBER)
                                        .optional().description("선택 기간 증가율. 계산할 수 없거나 지표가 없으면 null"),
                                fieldWithPath("data.content[].savedAt").type(JsonFieldType.STRING)
                                        .description("저장 시각"),
                                fieldWithPath("data.page").type(JsonFieldType.NUMBER).description("현재 페이지"),
                                fieldWithPath("data.size").type(JsonFieldType.NUMBER).description("페이지 크기"),
                                fieldWithPath("data.hasNext").type(JsonFieldType.BOOLEAN).description("다음 페이지 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("기간을 생략하면 저장한 트렌드를 24H 기준으로 조회한다")
    void getsSavedTrendsWithDefaultPeriod() throws Exception {
        // given
        given(savedTrendService.getSavedTrends(MEMBER_ID, AnalysisPeriod.HOURS_24, 0, 20))
                .willReturn(new SavedTrendListResponse(List.of(), 0, 20, false));

        // when
        mockMvc.perform(get("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content").isEmpty());

        // then
        then(savedTrendService).should()
                .getSavedTrends(MEMBER_ID, AnalysisPeriod.HOURS_24, 0, 20);
    }

    @Test
    @DisplayName("저장한 트렌드 조회 기간이 올바르지 않으면 400으로 응답한다")
    void rejectsInvalidSavedTrendPeriod() throws Exception {
        // when & then
        mockMvc.perform(get("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("period", "1Y"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."));

        then(savedTrendService).should(never()).getSavedTrends(any(), any(), any(Integer.class), any(Integer.class));
    }

    @Test
    @DisplayName("인증된 회원이 관심 키워드를 등록하면 201로 응답하고 문서화한다")
    void registersInterestKeyword() throws Exception {
        // given
        given(interestKeywordService.register(any(Long.class), any(InterestKeywordRegisterRequest.class)))
                .willReturn(new InterestKeywordRegisterResponse(10L, KEYWORD_ID, "Ballet Sneakers"));

        // when & then
        mockMvc.perform(post(URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"keywordId\":81}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.interestKeywordId").value(10))
                .andExpect(jsonPath("$.data.keywordId").value(81))
                .andExpect(jsonPath("$.data.keyword").value("Ballet Sneakers"))
                .andDo(document("members-interest-keywords-register",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        requestFields(fieldWithPath("keywordId").type(JsonFieldType.NUMBER)
                                .description("등록할 키워드 ID")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data.interestKeywordId").type(JsonFieldType.NUMBER)
                                        .description("관심 키워드 등록 ID"),
                                fieldWithPath("data.keywordId").type(JsonFieldType.NUMBER).description("키워드 ID"),
                                fieldWithPath("data.keyword").type(JsonFieldType.STRING).description("키워드 이름"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("이미 등록한 관심 키워드를 다시 요청하면 409로 응답한다")
    void rejectsDuplicateInterestKeyword() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INTEREST_KEYWORD_ALREADY_EXISTS))
                .given(interestKeywordService).register(any(Long.class), any(InterestKeywordRegisterRequest.class));

        // when & then
        mockMvc.perform(post(URL).header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON).content("{\"keywordId\":81}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value("이미 등록된 관심 키워드입니다."));
    }

    @Test
    @DisplayName("존재하지 않는 키워드를 등록하면 404로 응답한다")
    void rejectsUnknownKeyword() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.KEYWORD_NOT_FOUND))
                .given(interestKeywordService).register(any(Long.class), any(InterestKeywordRegisterRequest.class));

        // when & then
        mockMvc.perform(post(URL).header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON).content("{\"keywordId\":999}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 키워드입니다."));
    }

    @Test
    @DisplayName("키워드 ID가 없으면 400으로 응답하고 서비스를 호출하지 않는다")
    void rejectsMissingKeywordId() throws Exception {
        // when
        mockMvc.perform(post(URL).header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("키워드 ID는 필수입니다."));

        // then
        then(interestKeywordService).should(never()).register(any(), any());
    }

    @Test
    @DisplayName("인증 토큰이 없으면 401로 응답한다")
    void rejectsUnauthenticatedRequest() throws Exception {
        // when & then
        mockMvc.perform(post(URL).contentType(MediaType.APPLICATION_JSON).content("{\"keywordId\":81}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
    }

    @Test
    @DisplayName("인증된 회원의 추천 키워드를 반환하고 문서화한다")
    void getsRecommendedKeywords() throws Exception {
        // given
        given(interestKeywordService.getRecommendedKeywords(MEMBER_ID)).willReturn(List.of(
                new RecommendedKeywordResponse(82L, "Mary Jane Sneakers",
                        new DomainResponse(Domain.FASHION, "패션"), new BigDecimal("91.50"))));

        // when & then
        mockMvc.perform(get("/members/me/recommended-keywords")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].keywordId").value(82))
                .andExpect(jsonPath("$.data[0].keyword").value("Mary Jane Sneakers"))
                .andExpect(jsonPath("$.data[0].domain.code").value("FASHION"))
                .andExpect(jsonPath("$.data[0].domain.name").value("패션"))
                .andExpect(jsonPath("$.data[0].relationScore").value(91.50))
                .andDo(document("members-recommended-keywords",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data[].keywordId").type(JsonFieldType.NUMBER).description("추천 키워드 ID"),
                                fieldWithPath("data[].keyword").type(JsonFieldType.STRING).description("추천 키워드 이름"),
                                fieldWithPath("data[].domain.code").type(JsonFieldType.STRING).description("분야 코드"),
                                fieldWithPath("data[].domain.name").type(JsonFieldType.STRING).description("분야 이름"),
                                fieldWithPath("data[].relationScore").type(JsonFieldType.NUMBER)
                                        .description("관심 키워드와의 최고 연관도 점수"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("추천 키워드가 없으면 빈 배열을 반환한다")
    void returnsEmptyRecommendedKeywords() throws Exception {
        // given
        given(interestKeywordService.getRecommendedKeywords(MEMBER_ID)).willReturn(List.of());

        // when & then
        mockMvc.perform(get("/members/me/recommended-keywords")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("로그인 회원의 관심 키워드 목록을 조회하고 문서화한다")
    void getsInterestKeywords() throws Exception {
        // given
        given(interestKeywordService.getInterestKeywords(MEMBER_ID, Domain.DEVELOP))
                .willReturn(List.of(new InterestKeywordResponse(
                        15L, 50L, "Kubernetes", Domain.DEVELOP)));

        // when & then
        mockMvc.perform(get(URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("domain", "DEVELOP"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].interestKeywordId").value(15))
                .andExpect(jsonPath("$.data[0].keywordId").value(50))
                .andExpect(jsonPath("$.data[0].keyword").value("Kubernetes"))
                .andExpect(jsonPath("$.data[0].domain").value("DEVELOP"))
                .andDo(document("members-interest-keywords-list",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        queryParameters(parameterWithName("domain").optional()
                                .description("선택 분야: DEVELOP, FASHION")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data[].interestKeywordId").type(JsonFieldType.NUMBER)
                                        .description("관심 키워드 등록 ID"),
                                fieldWithPath("data[].keywordId").type(JsonFieldType.NUMBER).description("키워드 ID"),
                                fieldWithPath("data[].keyword").type(JsonFieldType.STRING).description("키워드명"),
                                fieldWithPath("data[].domain").type(JsonFieldType.STRING).description("분야 코드"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("관심 키워드가 없으면 빈 배열을 반환한다")
    void returnsEmptyInterestKeywords() throws Exception {
        // given
        given(interestKeywordService.getInterestKeywords(MEMBER_ID, null)).willReturn(List.of());

        // when & then
        mockMvc.perform(get(URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isEmpty());
    }

    @Test
    @DisplayName("로그인 회원이 소유한 관심 키워드를 삭제하고 문서화한다")
    void deletesInterestKeyword() throws Exception {
        // when & then
        mockMvc.perform(delete(URL + "/{interestKeywordId}", 15L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(org.hamcrest.Matchers.nullValue()))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-interest-keywords-delete",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        pathParameters(parameterWithName("interestKeywordId")
                                .description("삭제할 관심 키워드 등록 ID")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.NULL).description("삭제 성공 시 null"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
        then(interestKeywordService).should().delete(MEMBER_ID, 15L);
    }

    @Test
    @DisplayName("존재하지 않거나 본인 소유가 아닌 관심 키워드 삭제는 404로 응답한다")
    void rejectsUnknownInterestKeywordDeletion() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INTEREST_KEYWORD_NOT_FOUND))
                .given(interestKeywordService).delete(MEMBER_ID, 15L);

        // when & then
        mockMvc.perform(delete(URL + "/{interestKeywordId}", 15L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 관심 키워드입니다."));
    }


    @Test
    @DisplayName("인증된 회원이 본인 정보를 조회하면 200으로 응답하고 문서화한다")
    void returnsMyInfo() throws Exception {
        // given
        given(memberService.getMyInfo(MEMBER_ID))
                .willReturn(new MemberInfoResponse(MEMBER_ID, "test@example.com", "trenduser", false));

        // when & then
        mockMvc.perform(get(ME_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.memberId").value(1))
                .andExpect(jsonPath("$.data.email").value("test@example.com"))
                .andExpect(jsonPath("$.data.nickname").value("trenduser"))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-me",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.memberId").type(JsonFieldType.NUMBER)
                                        .description("회원 식별자. 액세스 토큰이 가리키는 본인의 ID"),
                                fieldWithPath("data.email").type(JsonFieldType.STRING)
                                        .description("가입 이메일"),
                                fieldWithPath("data.nickname").type(JsonFieldType.STRING)
                                        .description("닉네임"),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. false면 관심 분야 선택 화면으로 보낸다."),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("토큰의 회원 식별자로 서비스를 호출한다")
    void passesAuthenticatedMemberId() throws Exception {
        // given
        given(memberService.getMyInfo(MEMBER_ID))
                .willReturn(new MemberInfoResponse(MEMBER_ID, "test@example.com", "trenduser", false));

        // when
        mockMvc.perform(get(ME_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk());

        // then
        then(memberService).should().getMyInfo(MEMBER_ID);
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 401로 응답하고 서비스를 호출하지 않는다")
    void requiresAccessToken() throws Exception {
        // when & then
        mockMvc.perform(get(ME_URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."))
                .andDo(document("members-me-unauthorized",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
        then(memberService).should(never()).getMyInfo(any());
    }

    @Test
    @DisplayName("위조된 액세스 토큰이면 401로 응답한다")
    void rejectsForgedAccessToken() throws Exception {
        // when & then
        mockMvc.perform(get(ME_URL).header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("유효하지 않은 토큰입니다."));
        then(memberService).should(never()).getMyInfo(any());
    }

    @Test
    @DisplayName("토큰의 회원이 남아 있지 않으면 404로 응답한다")
    void returnsNotFoundForMissingMember() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.MEMBER_NOT_FOUND))
                .given(memberService).getMyInfo(MEMBER_ID);

        // when & then
        mockMvc.perform(get(ME_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("존재하지 않는 회원입니다."))
                .andDo(document("members-me-not-found",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
    }

    @Test
    @DisplayName("인증된 회원이 닉네임을 수정하면 200과 바뀐 정보를 반환하고 문서화한다")
    void updatesMyInfo() throws Exception {
        // given
        given(memberService.updateMyInfo(eq(MEMBER_ID), any(MemberUpdateRequest.class)))
                .willReturn(new MemberInfoResponse(MEMBER_ID, "test@example.com", "newNickname", false));

        // when & then
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_UPDATE_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.memberId").value(1))
                .andExpect(jsonPath("$.data.email").value("test@example.com"))
                .andExpect(jsonPath("$.data.nickname").value("newNickname"))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-me-update",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        requestFields(fieldWithPath("nickname").type(JsonFieldType.STRING)
                                .description("바꿀 닉네임. 필수, 앞뒤 공백 제거 후 2~30자. 현재 수정 가능한 필드는 닉네임뿐이다.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.memberId").type(JsonFieldType.NUMBER)
                                        .description("회원 식별자"),
                                fieldWithPath("data.email").type(JsonFieldType.STRING)
                                        .description("가입 이메일. 이 API로는 수정할 수 없다."),
                                fieldWithPath("data.nickname").type(JsonFieldType.STRING)
                                        .description("수정된 닉네임"),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. 수정으로 바뀌지 않는다."),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("토큰의 회원 식별자로 서비스를 호출한다")
    void passesAuthenticatedMemberIdOnUpdate() throws Exception {
        // given
        given(memberService.updateMyInfo(eq(MEMBER_ID), any(MemberUpdateRequest.class)))
                .willReturn(new MemberInfoResponse(MEMBER_ID, "test@example.com", "newNickname", false));

        // when
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_UPDATE_REQUEST))
                .andExpect(status().isOk());

        // then
        then(memberService).should().updateMyInfo(eq(MEMBER_ID), any(MemberUpdateRequest.class));
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 401로 응답하고 서비스를 호출하지 않는다")
    void updateRequiresAccessToken() throws Exception {
        // when & then
        mockMvc.perform(patch(ME_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_UPDATE_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."))
                .andDo(document("members-me-update-unauthorized",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
        then(memberService).should(never()).updateMyInfo(any(), any(MemberUpdateRequest.class));
    }

    @Test
    @DisplayName("앞뒤 공백을 제거하면 2자 미만이 되는 닉네임은 400으로 응답한다")
    void updateRejectsBlankPaddedNickname() throws Exception {
        // when & then
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(SHORT_NICKNAME_REQUEST))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("닉네임은 2자 이상 30자 이하여야 합니다."))
                .andDo(document("members-me-update-invalid-request",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )));
    }

    @Test
    @DisplayName("닉네임이 30자를 넘으면 400으로 응답한다")
    void updateRejectsTooLongNickname() throws Exception {
        // given
        String request = "{\"nickname\":\"" + "a".repeat(31) + "\"}";

        // when & then
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("닉네임은 2자 이상 30자 이하여야 합니다."));
    }

    @Test
    @DisplayName("닉네임이 없으면 400으로 응답하고 서비스를 호출하지 않는다")
    void updateRejectsMissingNickname() throws Exception {
        // when & then
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("닉네임은 필수입니다."));
        then(memberService).should(never()).updateMyInfo(any(), any(MemberUpdateRequest.class));
    }

    @Test
    @DisplayName("토큰의 회원이 남아 있지 않으면 404로 응답한다")
    void updateReturnsNotFoundForMissingMember() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.MEMBER_NOT_FOUND))
                .given(memberService).updateMyInfo(eq(MEMBER_ID), any(MemberUpdateRequest.class));

        // when & then
        mockMvc.perform(patch(ME_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_UPDATE_REQUEST))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 회원입니다."));
    }
    private String bearerToken() {
        return "Bearer " + jwtTokenProvider.issue(MEMBER_ID).accessToken();
    }
}
