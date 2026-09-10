package com.forever102.member.controller;

import static org.mockito.ArgumentMatchers.any;
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
import com.forever102.member.dto.RecommendedKeywordResponse;
import com.forever102.member.dto.RecommendedKeywordResponse.DomainResponse;
import com.forever102.member.service.MemberInterestKeywordService;
import com.forever102.member.service.MemberService;
import com.forever102.member.domain.Domain;
import java.math.BigDecimal;
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
    private static final Long MEMBER_ID = 1L;
    private static final Long KEYWORD_ID = 81L;

    @Autowired MockMvc mockMvc;
    @Autowired JwtTokenProvider jwtTokenProvider;
    @MockitoBean MemberInterestKeywordService interestKeywordService;
    @MockitoBean MemberService memberService;

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
    private String bearerToken() {
        return "Bearer " + jwtTokenProvider.issue(MEMBER_ID).accessToken();
    }
}
