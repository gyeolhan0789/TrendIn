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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.global.config.SecurityTestConfig;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
import com.forever102.member.dto.MemberDomainUpdateRequest;
import com.forever102.member.dto.InterestKeywordRegisterRequest;
import com.forever102.member.dto.InterestKeywordRegisterResponse;
import com.forever102.member.dto.InterestKeywordResponse;
import com.forever102.member.dto.MemberInfoResponse;
import com.forever102.member.dto.MemberUpdateRequest;
import com.forever102.member.dto.RecommendedKeywordResponse;
import com.forever102.member.dto.RecommendedKeywordResponse.DomainResponse;
import com.forever102.member.dto.SavedTrendListResponse;
import com.forever102.member.dto.SavedTrendListResponse.SavedTrendResponse;
import com.forever102.member.dto.SavedTrendRegisterRequest;
import com.forever102.member.dto.SavedTrendRegisterResponse;
import com.forever102.member.service.MemberDomainService;
import com.forever102.member.service.MemberInterestKeywordService;
import com.forever102.member.service.MemberService;
import com.forever102.member.service.SavedTrendService;
import com.forever102.member.domain.Domain;
import com.forever102.notification.domain.NotificationType;
import com.forever102.notification.dto.NotificationListResponse;
import com.forever102.notification.dto.NotificationListResponse.NotificationResponse;
import com.forever102.notification.dto.UnreadNotificationCountResponse;
import com.forever102.notification.dto.NotificationSettingResponse;
import com.forever102.notification.dto.NotificationSettingUpdateRequest;
import com.forever102.notification.service.NotificationQueryService;
import com.forever102.notification.service.NotificationReadService;
import com.forever102.notification.service.NotificationSettingService;
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
import org.springframework.restdocs.payload.FieldDescriptor;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(MemberController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class MemberControllerTest {

    private static final String URL = "/members/me/interest-keywords";
    private static final String ME_URL = "/members/me";
    private static final String MY_DOMAINS_URL = "/members/me/domains";
    private static final String VALID_DOMAINS_REQUEST = "{\"domains\":[\"DEVELOP\",\"FASHION\"]}";
    private static final String VALID_UPDATE_REQUEST = "{\"nickname\":\"newNickname\"}";
    private static final String SHORT_NICKNAME_REQUEST = "{\"nickname\":\"  a  \"}";
    private static final Long MEMBER_ID = 1L;
    private static final Long KEYWORD_ID = 81L;

    @Autowired MockMvc mockMvc;
    @Autowired JwtTokenProvider jwtTokenProvider;
    @MockitoBean MemberInterestKeywordService interestKeywordService;
    @MockitoBean MemberService memberService;
    @MockitoBean MemberDomainService memberDomainService;
    @MockitoBean SavedTrendService savedTrendService;
    @MockitoBean NotificationQueryService notificationQueryService;
    @MockitoBean NotificationReadService notificationReadService;
    @MockitoBean NotificationSettingService notificationSettingService;

    @Test
    @DisplayName("로그인한 회원의 알림 설정을 조회한다")
    void getsNotificationSettings() throws Exception {
        NotificationSettingResponse response = new NotificationSettingResponse(true, false, true, false);
        given(notificationSettingService.getSettings(MEMBER_ID)).willReturn(response);

        mockMvc.perform(get("/members/me/notification-settings")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.keywordSurgeEnabled").value(true))
                .andExpect(jsonPath("$.data.keywordDropEnabled").value(false))
                .andExpect(jsonPath("$.data.newTrendEnabled").value(true))
                .andExpect(jsonPath("$.data.trendTurningPointEnabled").value(false))
                .andDo(document("members-notification-settings-get",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        responseFields(notificationSettingResponseFields())));
    }

    @Test
    @DisplayName("로그인한 회원의 알림 설정을 수정한다")
    void updatesNotificationSettings() throws Exception {
        NotificationSettingResponse response = new NotificationSettingResponse(false, true, false, true);
        given(notificationSettingService.updateSettings(eq(MEMBER_ID),
                any(NotificationSettingUpdateRequest.class))).willReturn(response);

        mockMvc.perform(put("/members/me/notification-settings")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"keywordSurgeEnabled":false,"keywordDropEnabled":true,
                                 "newTrendEnabled":false,"trendTurningPointEnabled":true}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.keywordSurgeEnabled").value(false))
                .andExpect(jsonPath("$.data.keywordDropEnabled").value(true))
                .andDo(document("members-notification-settings-update",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        requestFields(
                                fieldWithPath("keywordSurgeEnabled").type(JsonFieldType.BOOLEAN)
                                        .description("키워드 급등 알림 활성화 여부"),
                                fieldWithPath("keywordDropEnabled").type(JsonFieldType.BOOLEAN)
                                        .description("키워드 급락 알림 활성화 여부"),
                                fieldWithPath("newTrendEnabled").type(JsonFieldType.BOOLEAN)
                                        .description("신규 트렌드 발견 알림 활성화 여부"),
                                fieldWithPath("trendTurningPointEnabled").type(JsonFieldType.BOOLEAN)
                                        .description("트렌드 전환점 알림 활성화 여부")
                        ),
                        responseFields(notificationSettingResponseFields())));
    }

    @Test
    @DisplayName("알림 설정 필드가 누락되면 400으로 응답한다")
    void rejectsIncompleteNotificationSettings() throws Exception {
        mockMvc.perform(put("/members/me/notification-settings")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());
        then(notificationSettingService).should(never()).updateSettings(any(), any());
    }

    @Test
    @DisplayName("로그인한 회원의 알림을 읽음 처리하고 문서화한다")
    void marksNotificationAsRead() throws Exception {
        // when & then
        mockMvc.perform(patch("/members/me/notifications/{notificationId}", 30L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(org.hamcrest.Matchers.nullValue()))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-notifications-read",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        pathParameters(parameterWithName("notificationId")
                                .description("읽음 처리할 알림 식별자")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.NULL)
                                        .description("읽음 처리 성공 시 null"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
        then(notificationReadService).should().markAsRead(MEMBER_ID, 30L);
    }

    @Test
    @DisplayName("존재하지 않거나 본인 소유가 아닌 알림 읽음 처리는 404로 응답한다")
    void rejectsUnknownNotificationRead() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.NOTIFICATION_NOT_FOUND))
                .given(notificationReadService).markAsRead(MEMBER_ID, 30L);

        // when & then
        mockMvc.perform(patch("/members/me/notifications/{notificationId}", 30L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 알림입니다."));
    }

    @Test
    @DisplayName("로그인한 회원의 미읽음 알림을 모두 읽음 처리하고 문서화한다")
    void marksAllNotificationsAsRead() throws Exception {
        // when & then
        mockMvc.perform(patch("/members/me/notifications/read-all")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(org.hamcrest.Matchers.nullValue()))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-notifications-read-all",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.NULL)
                                        .description("전체 읽음 처리 성공 시 null"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
        then(notificationReadService).should().markAllAsRead(MEMBER_ID);
    }

    @Test
    @DisplayName("로그인한 회원의 알림을 최신순 페이지로 조회하고 문서화한다")
    void getsNotifications() throws Exception {
        // given
        OffsetDateTime createdAt = OffsetDateTime.parse("2026-09-11T00:00:00+09:00");
        NotificationListResponse response = new NotificationListResponse(List.of(
                new NotificationResponse(30L, 101L, NotificationType.TREND_CHANGE,
                        "관심 키워드 '발레코어'가 급상승 트렌드에 포함되었어요.",
                        false, createdAt)), 0, 20, false);
        given(notificationQueryService.getNotifications(MEMBER_ID, 0, 20)).willReturn(response);

        // when & then
        mockMvc.perform(get("/members/me/notifications")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .queryParam("page", "0")
                        .queryParam("size", "20"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.content[0].notificationId").value(30))
                .andExpect(jsonPath("$.data.content[0].trendId").value(101))
                .andExpect(jsonPath("$.data.content[0].notificationType").value("TREND_CHANGE"))
                .andExpect(jsonPath("$.data.content[0].message")
                        .value("관심 키워드 '발레코어'가 급상승 트렌드에 포함되었어요."))
                .andExpect(jsonPath("$.data.content[0].isRead").value(false))
                .andExpect(jsonPath("$.data.content[0].createdAt")
                        .value("2026-09-11T00:00:00+09:00"))
                .andExpect(jsonPath("$.data.page").value(0))
                .andExpect(jsonPath("$.data.size").value(20))
                .andExpect(jsonPath("$.data.hasNext").value(false))
                .andDo(document("members-notifications-list",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        queryParameters(
                                parameterWithName("page").optional()
                                        .description("페이지 번호. 0부터 시작하며 기본값은 0"),
                                parameterWithName("size").optional()
                                        .description("페이지 크기. 기본값은 20")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.content[].notificationId").type(JsonFieldType.NUMBER)
                                        .description("알림 식별자"),
                                fieldWithPath("data.content[].trendId").type(JsonFieldType.NUMBER)
                                        .description("알림 대상 트렌드 식별자"),
                                fieldWithPath("data.content[].notificationType").type(JsonFieldType.STRING)
                                        .description("알림 유형"),
                                fieldWithPath("data.content[].message").type(JsonFieldType.STRING)
                                        .description("알림 메시지"),
                                fieldWithPath("data.content[].isRead").type(JsonFieldType.BOOLEAN)
                                        .description("읽음 여부"),
                                fieldWithPath("data.content[].createdAt").type(JsonFieldType.STRING)
                                        .description("알림 생성 시각"),
                                fieldWithPath("data.page").type(JsonFieldType.NUMBER)
                                        .description("현재 페이지 번호"),
                                fieldWithPath("data.size").type(JsonFieldType.NUMBER)
                                        .description("페이지 크기"),
                                fieldWithPath("data.hasNext").type(JsonFieldType.BOOLEAN)
                                        .description("다음 페이지 존재 여부"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("로그인한 회원의 읽지 않은 알림 개수를 조회하고 문서화한다")
    void getsUnreadNotificationCount() throws Exception {
        // given
        given(notificationQueryService.getUnreadCount(MEMBER_ID))
                .willReturn(new UnreadNotificationCountResponse(3L));

        // when & then
        mockMvc.perform(get("/members/me/notifications/unread-count")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.unreadCount").value(3))
                .andDo(document("members-notifications-unread-count",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.unreadCount").type(JsonFieldType.NUMBER)
                                        .description("읽지 않은 알림 개수"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("알림 목록의 page와 size를 생략하면 기본값으로 조회한다")
    void getsNotificationsWithDefaultPagination() throws Exception {
        // given
        given(notificationQueryService.getNotifications(MEMBER_ID, 0, 20))
                .willReturn(new NotificationListResponse(List.of(), 0, 20, false));

        // when
        mockMvc.perform(get("/members/me/notifications")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.content").isEmpty());

        // then
        then(notificationQueryService).should().getNotifications(MEMBER_ID, 0, 20);
    }

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
    @DisplayName("인증된 회원이 트렌드를 저장하면 201로 응답하고 문서화한다")
    void registersSavedTrend() throws Exception {
        // given
        OffsetDateTime savedAt = OffsetDateTime.parse("2026-08-31T09:00:00+09:00");
        given(savedTrendService.register(eq(MEMBER_ID), any(SavedTrendRegisterRequest.class)))
                .willReturn(new SavedTrendRegisterResponse(15L, 101L, savedAt));

        // when & then
        mockMvc.perform(post("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"trendId\":101}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.savedTrendId").value(15))
                .andExpect(jsonPath("$.data.trendId").value(101))
                .andExpect(jsonPath("$.data.savedAt")
                        .value("2026-08-31T09:00:00+09:00"))
                .andDo(document("members-saved-trends-register",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        requestFields(fieldWithPath("trendId").type(JsonFieldType.NUMBER)
                                .description("저장할 트렌드 ID")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.savedTrendId").type(JsonFieldType.NUMBER)
                                        .description("저장 트렌드 ID"),
                                fieldWithPath("data.trendId").type(JsonFieldType.NUMBER)
                                        .description("트렌드 ID"),
                                fieldWithPath("data.savedAt").type(JsonFieldType.STRING)
                                        .description("저장 시각"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
    }

    @Test
    @DisplayName("동일한 트렌드를 다시 저장하면 409로 응답한다")
    void rejectsDuplicateSavedTrend() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.SAVED_TREND_ALREADY_EXISTS))
                .given(savedTrendService).register(eq(MEMBER_ID), any(SavedTrendRegisterRequest.class));

        // when & then
        mockMvc.perform(post("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"trendId\":101}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value("이미 저장한 트렌드입니다."));
    }

    @Test
    @DisplayName("존재하지 않는 트렌드를 저장하면 404로 응답한다")
    void rejectsUnknownTrendSave() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.TREND_NOT_FOUND))
                .given(savedTrendService).register(eq(MEMBER_ID), any(SavedTrendRegisterRequest.class));

        // when & then
        mockMvc.perform(post("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"trendId\":999}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 트렌드입니다."));
    }

    @Test
    @DisplayName("트렌드 ID 없이 저장을 요청하면 400으로 응답한다")
    void rejectsMissingSavedTrendId() throws Exception {
        // when & then
        mockMvc.perform(post("/members/me/saved-trends")
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("트렌드 ID는 필수입니다."));
        then(savedTrendService).should(never()).register(any(), any());
    }

    @Test
    @DisplayName("로그인한 회원이 본인의 저장 트렌드를 해제하고 문서화한다")
    void deletesSavedTrend() throws Exception {
        // when & then
        mockMvc.perform(delete("/members/me/saved-trends/{savedTrendId}", 15L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(org.hamcrest.Matchers.nullValue()))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-saved-trends-delete",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰")),
                        pathParameters(parameterWithName("savedTrendId")
                                .description("해제할 저장 트렌드 ID")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.NULL)
                                        .description("저장 해제 성공 시 null"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null"))));
        then(savedTrendService).should().delete(MEMBER_ID, 15L);
    }

    @Test
    @DisplayName("존재하지 않거나 본인 소유가 아닌 저장 트렌드 해제는 404로 응답한다")
    void rejectsUnknownSavedTrendDeletion() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.SAVED_TREND_NOT_FOUND))
                .given(savedTrendService).delete(MEMBER_ID, 15L);

        // when & then
        mockMvc.perform(delete("/members/me/saved-trends/{savedTrendId}", 15L)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("존재하지 않는 저장 트렌드입니다."));
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

    @Test
    @DisplayName("인증된 회원이 선택한 분야를 조회하면 200으로 응답하고 문서화한다")
    void returnsMyDomains() throws Exception {
        // given
        given(memberDomainService.getMyDomains(MEMBER_ID)).willReturn(List.of(
                new com.forever102.member.dto.DomainResponse(Domain.DEVELOP, "개발"),
                new com.forever102.member.dto.DomainResponse(Domain.FASHION, "패션")));

        // when & then
        mockMvc.perform(get(MY_DOMAINS_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].domain").value("DEVELOP"))
                .andExpect(jsonPath("$.data[0].name").value("개발"))
                .andExpect(jsonPath("$.data[1].domain").value("FASHION"))
                .andExpect(jsonPath("$.data[1].name").value("패션"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-me-domains",
                        preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data[].domain").type(JsonFieldType.STRING)
                                        .description("분야 코드. 전체 분야 조회의 domain과 같은 값이다."),
                                fieldWithPath("data[].name").type(JsonFieldType.STRING)
                                        .description("화면에 표시할 분야 이름"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("아직 분야를 고르지 않았으면 200과 빈 배열을 반환한다")
    void returnsEmptyArrayBeforeFirstRegistration() throws Exception {
        // given
        given(memberDomainService.getMyDomains(MEMBER_ID)).willReturn(List.of());

        // when & then
        mockMvc.perform(get(MY_DOMAINS_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").isArray())
                .andExpect(jsonPath("$.data").isEmpty())
                .andDo(document("members-me-domains-empty",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.ARRAY)
                                        .description("선택한 분야가 없으면 빈 배열. 오류가 아니다."),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("토큰의 회원 식별자로 서비스를 호출한다")
    void passesAuthenticatedMemberIdOnDomainLookup() throws Exception {
        // given
        given(memberDomainService.getMyDomains(MEMBER_ID)).willReturn(List.of());

        // when
        mockMvc.perform(get(MY_DOMAINS_URL).header(HttpHeaders.AUTHORIZATION, bearerToken()))
                .andExpect(status().isOk());

        // then
        then(memberDomainService).should().getMyDomains(MEMBER_ID);
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 401로 응답하고 서비스를 호출하지 않는다")
    void myDomainsRequiresAccessToken() throws Exception {
        // when & then
        mockMvc.perform(get(MY_DOMAINS_URL))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."))
                .andDo(document("members-me-domains-unauthorized",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
        then(memberDomainService).should(never()).getMyDomains(any());
    }

    @Test
    @DisplayName("인증된 회원이 관심 분야를 교체하면 200과 교체 결과를 반환하고 문서화한다")
    void updatesMyDomains() throws Exception {
        // given
        given(memberDomainService.updateMyDomains(eq(MEMBER_ID), any(MemberDomainUpdateRequest.class)))
                .willReturn(List.of(
                        new com.forever102.member.dto.DomainResponse(Domain.DEVELOP, "개발"),
                        new com.forever102.member.dto.DomainResponse(Domain.FASHION, "패션")));

        // when & then
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_DOMAINS_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data[0].domain").value("DEVELOP"))
                .andExpect(jsonPath("$.data[0].name").value("개발"))
                .andExpect(jsonPath("$.data[1].domain").value("FASHION"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.nullValue()))
                .andDo(document("members-me-domains-update",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        requestHeaders(headerWithName(HttpHeaders.AUTHORIZATION)
                                .description("Bearer 액세스 토큰. 필수.")),
                        requestFields(fieldWithPath("domains").type(JsonFieldType.ARRAY)
                                .description("교체할 분야 코드 목록. 필수, 최소 1개. 같은 값을 여러 번 보내면 하나로 합친다.")),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data[].domain").type(JsonFieldType.STRING)
                                        .description("교체 후 선택된 분야 코드"),
                                fieldWithPath("data[].name").type(JsonFieldType.STRING)
                                        .description("화면에 표시할 분야 이름"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )));
    }

    @Test
    @DisplayName("토큰의 회원 식별자로 서비스를 호출한다")
    void passesAuthenticatedMemberIdOnDomainUpdate() throws Exception {
        // given
        given(memberDomainService.updateMyDomains(eq(MEMBER_ID), any(MemberDomainUpdateRequest.class)))
                .willReturn(List.of());

        // when
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_DOMAINS_REQUEST))
                .andExpect(status().isOk());

        // then
        then(memberDomainService).should().updateMyDomains(eq(MEMBER_ID), any(MemberDomainUpdateRequest.class));
    }

    @Test
    @DisplayName("분야를 하나도 보내지 않으면 400으로 응답한다")
    void updateRejectsEmptyDomains() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INTEREST_COUNT_INVALID))
                .given(memberDomainService).updateMyDomains(eq(MEMBER_ID), any(MemberDomainUpdateRequest.class));

        // when & then
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"domains\":[]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("관심 분야는 최소 1개 이상 선택해야 합니다."))
                .andDo(document("members-me-domains-update-count-invalid",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
    }

    @Test
    @DisplayName("존재하지 않는 분야를 보내면 404로 응답한다")
    void updateRejectsUnknownDomain() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.DOMAIN_NOT_FOUND))
                .given(memberDomainService).updateMyDomains(eq(MEMBER_ID), any(MemberDomainUpdateRequest.class));

        // when & then
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"domains\":[\"COOKING\"]}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("존재하지 않는 분야입니다."))
                .andDo(document("members-me-domains-update-domain-not-found",
                        preprocessRequest(prettyPrint()), preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )));
    }

    @Test
    @DisplayName("domains 필드가 없으면 400으로 응답하고 서비스를 호출하지 않는다")
    void updateRejectsMissingDomainsField() throws Exception {
        // when & then
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("관심 분야 목록은 필수입니다."));
        then(memberDomainService).should(never())
                .updateMyDomains(any(), any(MemberDomainUpdateRequest.class));
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 401로 응답하고 서비스를 호출하지 않는다")
    void updateMyDomainsRequiresAccessToken() throws Exception {
        // when & then
        mockMvc.perform(put(MY_DOMAINS_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_DOMAINS_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."));
        then(memberDomainService).should(never())
                .updateMyDomains(any(), any(MemberDomainUpdateRequest.class));
    }

    private static List<FieldDescriptor> notificationSettingResponseFields() {
        return List.of(
                fieldWithPath("success").type(JsonFieldType.BOOLEAN).description("요청 성공 여부"),
                fieldWithPath("data").type(JsonFieldType.OBJECT).description("알림 설정"),
                fieldWithPath("data.keywordSurgeEnabled").type(JsonFieldType.BOOLEAN)
                        .description("키워드 급등 알림 활성화 여부"),
                fieldWithPath("data.keywordDropEnabled").type(JsonFieldType.BOOLEAN)
                        .description("키워드 급락 알림 활성화 여부"),
                fieldWithPath("data.newTrendEnabled").type(JsonFieldType.BOOLEAN)
                        .description("신규 트렌드 발견 알림 활성화 여부"),
                fieldWithPath("data.trendTurningPointEnabled").type(JsonFieldType.BOOLEAN)
                        .description("트렌드 전환점 알림 활성화 여부"),
                fieldWithPath("message").type(JsonFieldType.NULL).description("응답 메시지")
        );
    }

    private String bearerToken() {
        return "Bearer " + jwtTokenProvider.issue(MEMBER_ID).accessToken();
    }
}
