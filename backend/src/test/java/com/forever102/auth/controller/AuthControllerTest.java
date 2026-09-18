package com.forever102.auth.controller;

import static org.hamcrest.Matchers.nullValue;
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
import static org.springframework.restdocs.mockmvc.RestDocumentationRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.auth.dto.EmailCheckRequest;
import com.forever102.auth.dto.EmailCheckResponse;
import com.forever102.auth.dto.LoginRequest;
import com.forever102.auth.dto.LoginResponse;
import com.forever102.auth.dto.OAuthLoginRequest;
import com.forever102.auth.dto.OAuthLoginResponse;
import com.forever102.auth.dto.LogoutRequest;
import com.forever102.auth.dto.ReissueRequest;
import com.forever102.auth.dto.ReissueResponse;
import com.forever102.auth.dto.SignUpRequest;
import com.forever102.auth.dto.SignUpResponse;
import com.forever102.auth.jwt.JwtTokenProvider;
import com.forever102.auth.service.AuthService;
import com.forever102.auth.service.OAuthService;
import com.forever102.global.config.SecurityTestConfig;
import com.forever102.global.exception.BusinessException;
import com.forever102.global.exception.ErrorCode;
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

@WebMvcTest(AuthController.class)
@Import(SecurityTestConfig.class)
@AutoConfigureRestDocs
class AuthControllerTest {

    private static final String SIGN_UP_URL = "/auth/signup";
    private static final String VALID_REQUEST = """
            {
              "email": "test@example.com",
              "password": "password123!",
              "nickname": "trenduser"
            }
            """;

    private static final String EMAIL_CHECK_URL = "/auth/email-check";
    private static final String OAUTH_LOGIN_URL = "/auth/oauth/{provider}/login";
    private static final String VALID_OAUTH_REQUEST = "{\"code\":\"example-authorization-code\",\"state\":\"example-state\"}";
    private static final String VALID_EMAIL_CHECK_REQUEST = """
            {
              "email": "test@example.com"
            }
            """;

    private static final String LOGIN_URL = "/auth/login";
    private static final String VALID_LOGIN_REQUEST = """
            {
              "email": "test@example.com",
              "password": "password123!"
            }
            """;

    private static final String REISSUE_URL = "/auth/reissue";
    private static final String VALID_REISSUE_REQUEST = """
            {
              "refreshToken": "example-refresh-token"
            }
            """;

    private static final String LOGOUT_URL = "/auth/logout";
    private static final Long MEMBER_ID = 1L;
    private static final String VALID_LOGOUT_REQUEST = """
            {
              "refreshToken": "example-refresh-token"
            }
            """;
    private static final String BLANK_REFRESH_TOKEN_REQUEST = """
            {
              "refreshToken": "  "
            }
            """;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @MockitoBean
    private AuthService authService;

    @MockitoBean
    private OAuthService oauthService;

    @Test
    @DisplayName("유효한 요청이면 201과 생성된 회원 정보를 반환한다")
    void signUpReturnsCreated() throws Exception {
        // given
        given(authService.signUp(any(SignUpRequest.class)))
                .willReturn(new SignUpResponse(1L, "test@example.com", "trenduser", false));

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_REQUEST))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.memberId").value(1))
                .andExpect(jsonPath("$.data.email").value("test@example.com"))
                .andExpect(jsonPath("$.data.nickname").value("trenduser"))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andDo(document("auth-signup",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestFields(
                                fieldWithPath("email").type(JsonFieldType.STRING)
                                        .description("이메일. 필수, 이메일 형식, 최대 254자. 앞뒤 공백 제거 후 소문자로 정규화된다."),
                                fieldWithPath("password").type(JsonFieldType.STRING)
                                        .description("비밀번호. 필수, 8~128자, 영문·숫자·특수문자를 모두 포함."),
                                fieldWithPath("nickname").type(JsonFieldType.STRING)
                                        .description("닉네임. 필수, 앞뒤 공백 제거 후 2~30자.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.memberId").type(JsonFieldType.NUMBER)
                                        .description("생성된 회원 식별자"),
                                fieldWithPath("data.email").type(JsonFieldType.STRING)
                                        .description("정규화되어 저장된 이메일"),
                                fieldWithPath("data.nickname").type(JsonFieldType.STRING)
                                        .description("닉네임"),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. 가입 직후에는 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("이미 가입된 이메일이면 409로 응답한다")
    void signUpReturnsConflictForDuplicatedEmail() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.EMAIL_ALREADY_EXISTS))
                .given(authService).signUp(any(SignUpRequest.class));

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_REQUEST))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("이미 가입된 이메일입니다."))
                .andDo(document("auth-signup-email-already-exists",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("이메일 형식이 올바르지 않으면 400으로 응답한다")
    void signUpRejectsInvalidEmail() throws Exception {
        // given
        String request = """
                {
                  "email": "not-an-email",
                  "password": "password123!",
                  "nickname": "trenduser"
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("이메일 형식이 올바르지 않습니다."))
                .andDo(document("auth-signup-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("비밀번호가 8자 미만이면 400으로 응답한다")
    void signUpRejectsShortPassword() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": "pw1234!",
                  "nickname": "trenduser"
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("비밀번호는 8자 이상 128자 이하여야 합니다."));
    }

    @Test
    @DisplayName("비밀번호에 특수문자가 없으면 400으로 응답한다")
    void signUpRejectsPasswordWithoutSpecialCharacter() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": "password1234",
                  "nickname": "trenduser"
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("비밀번호는 영문, 숫자, 특수문자를 모두 포함해야 합니다."));
    }

    @Test
    @DisplayName("앞뒤 공백을 제거하면 2자 미만이 되는 닉네임은 400으로 응답한다")
    void signUpRejectsBlankPaddedNickname() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": "password123!",
                  "nickname": "  a  "
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("닉네임은 2자 이상 30자 이하여야 합니다."));
    }

    @Test
    @DisplayName("필수값이 누락되면 400으로 응답한다")
    void signUpRejectsMissingField() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": "password123!"
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    @DisplayName("본문이 올바른 JSON이 아니면 400으로 응답한다")
    void signUpRejectsMalformedJson() throws Exception {
        // given
        String request = "{ not json";

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."));
    }

    @Test
    @DisplayName("요청 검증에 실패하면 서비스를 호출하지 않는다")
    void signUpDoesNotCallServiceWhenInvalid() throws Exception {
        // given
        String request = """
                {
                  "email": "not-an-email",
                  "password": "password123!",
                  "nickname": "trenduser"
                }
                """;

        // when
        mockMvc.perform(post(SIGN_UP_URL)
                .contentType(MediaType.APPLICATION_JSON)
                .content(request));

        // then
        then(authService).should(never()).signUp(any(SignUpRequest.class));
    }

    @Test
    @DisplayName("이메일과 비밀번호가 일치하면 200과 발급된 토큰을 반환한다")
    void loginReturnsTokens() throws Exception {
        // given
        given(authService.login(any(LoginRequest.class)))
                .willReturn(new LoginResponse(
                        "example-access-token", "example-refresh-token", "Bearer", 900L, 1_209_600L, false));

        // when & then
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGIN_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.accessToken").value("example-access-token"))
                .andExpect(jsonPath("$.data.refreshToken").value("example-refresh-token"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.data.accessTokenExpiresIn").value(900))
                .andExpect(jsonPath("$.data.refreshTokenExpiresIn").value(1_209_600))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andDo(document("auth-login",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestFields(
                                fieldWithPath("email").type(JsonFieldType.STRING)
                                        .description("가입 이메일. 필수, 이메일 형식, 최대 254자. 앞뒤 공백 제거 후 소문자로 정규화된다."),
                                fieldWithPath("password").type(JsonFieldType.STRING)
                                        .description("가입 비밀번호. 필수, 최대 128자.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.accessToken").type(JsonFieldType.STRING)
                                        .description("API 호출에 사용하는 액세스 토큰"),
                                fieldWithPath("data.refreshToken").type(JsonFieldType.STRING)
                                        .description("액세스 토큰 재발급에 사용하는 리프레시 토큰. 회원당 하나만 유효하며 새로 로그인하면 이전 토큰은 무효가 된다."),
                                fieldWithPath("data.tokenType").type(JsonFieldType.STRING)
                                        .description("토큰 사용 방식. 항상 Bearer"),
                                fieldWithPath("data.accessTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("액세스 토큰의 유효 기간(초)"),
                                fieldWithPath("data.refreshTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("리프레시 토큰의 유효 기간(초)"),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. false면 관심 분야 선택 화면으로 보낸다."),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("이메일 또는 비밀번호가 일치하지 않으면 401로 응답한다")
    void loginReturnsUnauthorizedForInvalidCredentials() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INVALID_CREDENTIALS))
                .given(authService).login(any(LoginRequest.class));

        // when & then
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGIN_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("이메일 또는 비밀번호가 일치하지 않습니다."))
                .andDo(document("auth-login-invalid-credentials",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지. 계정 존재 여부를 구분해 노출하지 않도록 두 경우 모두 같은 메시지를 반환한다.")
                        )
                ));
    }

    @Test
    @DisplayName("이메일 형식이 올바르지 않으면 400으로 응답한다")
    void loginRejectsInvalidEmail() throws Exception {
        // given
        String request = """
                {
                  "email": "not-an-email",
                  "password": "password123!"
                }
                """;

        // when & then
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("이메일 형식이 올바르지 않습니다."))
                .andDo(document("auth-login-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("비밀번호가 비어 있으면 400으로 응답한다")
    void loginRejectsBlankPassword() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": ""
                }
                """;

        // when & then
        mockMvc.perform(post(LOGIN_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("비밀번호는 필수입니다."));
    }

    @Test
    @DisplayName("로그인 요청 검증에 실패하면 서비스를 호출하지 않는다")
    void loginDoesNotCallServiceWhenInvalid() throws Exception {
        // given
        String request = """
                {
                  "email": "not-an-email",
                  "password": "password123!"
                }
                """;

        // when
        mockMvc.perform(post(LOGIN_URL)
                .contentType(MediaType.APPLICATION_JSON)
                .content(request));

        // then
        then(authService).should(never()).login(any(LoginRequest.class));
    }

    @Test
    @DisplayName("유효한 리프레시 토큰이면 200과 새로 발급된 토큰을 반환한다")
    void reissueReturnsNewTokens() throws Exception {
        // given
        given(authService.reissue(any(ReissueRequest.class)))
                .willReturn(new ReissueResponse(
                        "example-access-token", "example-refresh-token", "Bearer", 900L, 1_209_600L, false));

        // when & then
        mockMvc.perform(post(REISSUE_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_REISSUE_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.accessToken").value("example-access-token"))
                .andExpect(jsonPath("$.data.refreshToken").value("example-refresh-token"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.data.accessTokenExpiresIn").value(900))
                .andExpect(jsonPath("$.data.refreshTokenExpiresIn").value(1_209_600))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andDo(document("auth-reissue",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestFields(
                                fieldWithPath("refreshToken").type(JsonFieldType.STRING)
                                        .description("로그인 또는 이전 재발급에서 받은 리프레시 토큰. 필수.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.accessToken").type(JsonFieldType.STRING)
                                        .description("새로 발급된 액세스 토큰"),
                                fieldWithPath("data.refreshToken").type(JsonFieldType.STRING)
                                        .description("새로 발급된 리프레시 토큰. 요청에 쓴 토큰은 이 시점부터 무효이므로 반드시 이 값으로 교체한다."),
                                fieldWithPath("data.tokenType").type(JsonFieldType.STRING)
                                        .description("토큰 사용 방식. 항상 Bearer"),
                                fieldWithPath("data.accessTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("액세스 토큰의 유효 기간(초)"),
                                fieldWithPath("data.refreshTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("리프레시 토큰의 유효 기간(초). 재발급 시점부터 다시 계산된다."),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. false면 관심 분야 선택 화면으로 보낸다."),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("리프레시 토큰이 유효하지 않거나 만료되었으면 401로 응답한다")
    void reissueReturnsUnauthorizedForInvalidRefreshToken() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INVALID_REFRESH_TOKEN))
                .given(authService).reissue(any(ReissueRequest.class));

        // when & then
        mockMvc.perform(post(REISSUE_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_REISSUE_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("유효하지 않거나 만료된 리프레시 토큰입니다."))
                .andDo(document("auth-reissue-invalid-refresh-token",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지. 서명 불일치·만료·이미 회전된 토큰을 구분해 노출하지 않는다.")
                        )
                ));
    }

    @Test
    @DisplayName("리프레시 토큰이 비어 있으면 400으로 응답한다")
    void reissueRejectsBlankRefreshToken() throws Exception {
        // given
        String request = """
                {
                  "refreshToken": "  "
                }
                """;

        // when & then
        mockMvc.perform(post(REISSUE_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("리프레시 토큰은 필수입니다."))
                .andDo(document("auth-reissue-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("리프레시 토큰 필드가 없으면 400으로 응답한다")
    void reissueRejectsMissingRefreshToken() throws Exception {
        mockMvc.perform(post(REISSUE_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    @DisplayName("재발급 요청 검증에 실패하면 서비스를 호출하지 않는다")
    void reissueDoesNotCallServiceWhenInvalid() throws Exception {
        // when
        mockMvc.perform(post(REISSUE_URL)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"));

        // then
        then(authService).should(never()).reissue(any(ReissueRequest.class));
    }

    @Test
    @DisplayName("인증된 회원이 현재 세션의 리프레시 토큰으로 요청하면 200으로 응답한다")
    void logoutReturnsOk() throws Exception {
        // when & then
        mockMvc.perform(post(LOGOUT_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGOUT_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data").value(nullValue()))
                .andExpect(jsonPath("$.message").value(nullValue()))
                .andDo(document("auth-logout",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestHeaders(
                                headerWithName(HttpHeaders.AUTHORIZATION)
                                        .description("Bearer 액세스 토큰. 필수.")
                        ),
                        requestFields(
                                fieldWithPath("refreshToken").type(JsonFieldType.STRING)
                                        .description("현재 로그인 세션의 리프레시 토큰. 필수. 액세스 토큰과 같은 회원의 것이어야 한다.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data").type(JsonFieldType.NULL)
                                        .description("반환 데이터 없음. 항상 null"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("로그아웃에 성공하면 인증된 회원 식별자로 서비스를 호출한다")
    void logoutPassesAuthenticatedMemberId() throws Exception {
        // when
        mockMvc.perform(post(LOGOUT_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGOUT_REQUEST))
                .andExpect(status().isOk());

        // then
        then(authService).should().logout(eq(MEMBER_ID), any(LogoutRequest.class));
    }

    @Test
    @DisplayName("현재 세션과 일치하지 않는 리프레시 토큰이면 401로 응답한다")
    void logoutReturnsUnauthorizedForMismatchedRefreshToken() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.INVALID_TOKEN))
                .given(authService).logout(any(Long.class), any(LogoutRequest.class));

        // when & then
        mockMvc.perform(post(LOGOUT_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGOUT_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("유효하지 않은 토큰입니다."))
                .andDo(document("auth-logout-invalid-token",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("액세스 토큰이 없으면 401로 응답하고 서비스를 호출하지 않는다")
    void logoutRequiresAccessToken() throws Exception {
        // when & then
        mockMvc.perform(post(LOGOUT_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_LOGOUT_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("인증이 필요합니다."))
                .andDo(document("auth-logout-unauthorized",
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )
                ));
        then(authService).should(never()).logout(any(), any(LogoutRequest.class));
    }

    @Test
    @DisplayName("리프레시 토큰이 비어 있으면 400으로 응답한다")
    void logoutRejectsBlankRefreshToken() throws Exception {
        // given
        String request = BLANK_REFRESH_TOKEN_REQUEST;

        // when & then
        mockMvc.perform(post(LOGOUT_URL)
                        .header(HttpHeaders.AUTHORIZATION, bearerToken())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("리프레시 토큰은 필수입니다."))
                .andDo(document("auth-logout-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("로그아웃 요청 검증에 실패하면 서비스를 호출하지 않는다")
    void logoutDoesNotCallServiceWhenInvalid() throws Exception {
        // when
        mockMvc.perform(post(LOGOUT_URL)
                .header(HttpHeaders.AUTHORIZATION, bearerToken())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"));

        // then
        then(authService).should(never()).logout(any(), any(LogoutRequest.class));
    }


    @Test
    @DisplayName("가입되지 않은 이메일이면 200과 available true를 반환한다")
    void checkEmailReturnsAvailable() throws Exception {
        // given
        given(authService.checkEmail(any(EmailCheckRequest.class)))
                .willReturn(new EmailCheckResponse(true));

        // when & then
        mockMvc.perform(post(EMAIL_CHECK_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_EMAIL_CHECK_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.available").value(true))
                .andExpect(jsonPath("$.message").value(nullValue()))
                .andDo(document("auth-email-check",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        requestFields(
                                fieldWithPath("email").type(JsonFieldType.STRING)
                                        .description("중복을 확인할 이메일. 필수, 이메일 형식, 최대 254자. 앞뒤 공백 제거 후 소문자로 정규화된다.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 중복 여부와 무관하게 확인에 성공하면 true"),
                                fieldWithPath("data.available").type(JsonFieldType.BOOLEAN)
                                        .description("사용 가능 여부. true면 가입 가능, false면 이미 사용 중인 이메일"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("이미 가입된 이메일이어도 200과 available false를 반환한다")
    void checkEmailReturnsUnavailable() throws Exception {
        // given
        given(authService.checkEmail(any(EmailCheckRequest.class)))
                .willReturn(new EmailCheckResponse(false));

        // when & then
        mockMvc.perform(post(EMAIL_CHECK_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_EMAIL_CHECK_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.available").value(false))
                .andDo(document("auth-email-check-unavailable",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 중복이어도 확인 자체는 성공이므로 true"),
                                fieldWithPath("data.available").type(JsonFieldType.BOOLEAN)
                                        .description("사용 가능 여부. 이미 가입된 이메일이므로 false"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("중복 확인은 토큰 없이 호출할 수 있다")
    void checkEmailIsPublic() throws Exception {
        // given
        given(authService.checkEmail(any(EmailCheckRequest.class)))
                .willReturn(new EmailCheckResponse(true));

        // when & then
        mockMvc.perform(post(EMAIL_CHECK_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_EMAIL_CHECK_REQUEST))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("이메일 형식이 올바르지 않으면 400으로 응답한다")
    void checkEmailRejectsInvalidEmail() throws Exception {
        // given
        String request = """
                {
                  "email": "not-an-email"
                }
                """;

        // when & then
        mockMvc.perform(post(EMAIL_CHECK_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("이메일 형식이 올바르지 않습니다."))
                .andDo(document("auth-email-check-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("이메일이 없으면 400으로 응답한다")
    void checkEmailRejectsMissingEmail() throws Exception {
        // when & then
        mockMvc.perform(post(EMAIL_CHECK_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("이메일은 필수입니다."));
    }

    @Test
    @DisplayName("중복 확인 요청 검증에 실패하면 서비스를 호출하지 않는다")
    void checkEmailDoesNotCallServiceWhenInvalid() throws Exception {
        // when
        mockMvc.perform(post(EMAIL_CHECK_URL)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"));

        // then
        then(authService).should(never()).checkEmail(any(EmailCheckRequest.class));
    }

    @Test
    @DisplayName("OAuth 인증에 성공하면 200과 발급된 토큰을 반환한다")
    void oauthLoginReturnsTokens() throws Exception {
        // given
        given(oauthService.login(eq("gitlab"), any(OAuthLoginRequest.class)))
                .willReturn(new OAuthLoginResponse(
                        "example-access-token", "example-refresh-token", "Bearer",
                        900L, 1_209_600L, true, false));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.accessToken").value("example-access-token"))
                .andExpect(jsonPath("$.data.refreshToken").value("example-refresh-token"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.data.accessTokenExpiresIn").value(900))
                .andExpect(jsonPath("$.data.refreshTokenExpiresIn").value(1_209_600))
                .andExpect(jsonPath("$.data.isNewMember").value(true))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false))
                .andDo(document("auth-oauth-login",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        pathParameters(parameterWithName("provider")
                                .description("OAuth 제공자 식별자. 현재 gitlab만 지원하며 대소문자를 가리지 않는다.")),
                        requestFields(
                                fieldWithPath("code").type(JsonFieldType.STRING)
                                        .description("제공자가 프론트엔드 콜백에 전달한 일회용 인가 코드. 필수."),
                                fieldWithPath("state").type(JsonFieldType.STRING)
                                        .description("제공자가 콜백에 반환한 state. 필수. CSRF 대조는 state를 만든 프런트가 수행한다.")
                        ),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부"),
                                fieldWithPath("data.accessToken").type(JsonFieldType.STRING)
                                        .description("API 호출에 사용하는 액세스 토큰"),
                                fieldWithPath("data.refreshToken").type(JsonFieldType.STRING)
                                        .description("액세스 토큰 재발급에 사용하는 리프레시 토큰"),
                                fieldWithPath("data.tokenType").type(JsonFieldType.STRING)
                                        .description("토큰 사용 방식. 항상 Bearer"),
                                fieldWithPath("data.accessTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("액세스 토큰의 유효 기간(초)"),
                                fieldWithPath("data.refreshTokenExpiresIn").type(JsonFieldType.NUMBER)
                                        .description("리프레시 토큰의 유효 기간(초)"),
                                fieldWithPath("data.isNewMember").type(JsonFieldType.BOOLEAN)
                                        .description("이번 요청으로 가입했는지 여부. true면 관심 분야 선택으로 보낸다."),
                                fieldWithPath("data.onboardingCompleted").type(JsonFieldType.BOOLEAN)
                                        .description("온보딩 완료 여부. 신규 가입 직후에는 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.NULL)
                                        .description("성공 응답에서는 항상 null")
                        )
                ));
    }

    @Test
    @DisplayName("이미 가입한 회원이면 isNewMember가 false다")
    void oauthLoginReportsExistingMember() throws Exception {
        // given
        given(oauthService.login(eq("gitlab"), any(OAuthLoginRequest.class)))
                .willReturn(new OAuthLoginResponse(
                        "example-access-token", "example-refresh-token", "Bearer",
                        900L, 1_209_600L, false, true));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.isNewMember").value(false))
                .andExpect(jsonPath("$.data.onboardingCompleted").value(true));
    }

    @Test
    @DisplayName("OAuth 로그인은 토큰 없이 호출할 수 있다")
    void oauthLoginIsPublic() throws Exception {
        // given
        given(oauthService.login(eq("gitlab"), any(OAuthLoginRequest.class)))
                .willReturn(new OAuthLoginResponse(
                        "example-access-token", "example-refresh-token", "Bearer",
                        900L, 1_209_600L, true, false));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("활성화하지 않은 제공자면 400으로 응답한다")
    void oauthLoginRejectsUnsupportedProvider() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.UNSUPPORTED_PROVIDER))
                .given(oauthService).login(eq("github"), any(OAuthLoginRequest.class));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "github")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.message").value("지원하지 않는 OAuth 제공자입니다."))
                .andDo(document("auth-oauth-login-unsupported-provider",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("OAuth 인증에 실패하면 401로 응답한다")
    void oauthLoginReturnsUnauthorized() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.OAUTH_AUTHENTICATION_FAILED))
                .given(oauthService).login(eq("gitlab"), any(OAuthLoginRequest.class));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("OAuth 인증에 실패했습니다."))
                .andDo(document("auth-oauth-login-authentication-failed",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지. 코드 만료·재사용과 제공자 계정 문제를 구분해 노출하지 않는다.")
                        )
                ));
    }

    @Test
    @DisplayName("제공자와 통신하지 못하면 502로 응답한다")
    void oauthLoginReturnsBadGateway() throws Exception {
        // given
        willThrow(new BusinessException(ErrorCode.OAUTH_PROVIDER_ERROR))
                .given(oauthService).login(eq("gitlab"), any(OAuthLoginRequest.class));

        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_OAUTH_REQUEST))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.message").value("OAuth 제공자와 통신하지 못했습니다."))
                .andDo(document("auth-oauth-login-provider-error",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("에러 메시지. 제공자 장애이므로 재시도할 수 있다.")
                        )
                ));
    }

    @Test
    @DisplayName("인가 코드가 없으면 400으로 응답한다")
    void oauthLoginRejectsMissingCode() throws Exception {
        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"state\":\"example-state\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("인가 코드는 필수입니다."))
                .andDo(document("auth-oauth-login-invalid-request",
                        preprocessRequest(prettyPrint()),
                        preprocessResponse(prettyPrint()),
                        responseFields(
                                fieldWithPath("success").type(JsonFieldType.BOOLEAN)
                                        .description("요청 성공 여부. 항상 false"),
                                fieldWithPath("message").type(JsonFieldType.STRING)
                                        .description("검증에 실패한 첫 번째 필드의 메시지")
                        )
                ));
    }

    @Test
    @DisplayName("state가 없으면 400으로 응답한다")
    void oauthLoginRejectsMissingState() throws Exception {
        // when & then
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"example-authorization-code\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("state는 필수입니다."));
    }

    @Test
    @DisplayName("요청 검증에 실패하면 서비스를 호출하지 않는다")
    void oauthLoginDoesNotCallServiceWhenInvalid() throws Exception {
        // when
        mockMvc.perform(post(OAUTH_LOGIN_URL, "gitlab")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"));

        // then
        then(oauthService).should(never()).login(any(), any(OAuthLoginRequest.class));
    }
    private String bearerToken() {
        return "Bearer " + jwtTokenProvider.issue(MEMBER_ID).accessToken();
    }
}
