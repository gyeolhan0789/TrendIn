package com.forever102.backend.auth.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.springframework.restdocs.mockmvc.MockMvcRestDocumentation.document;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessRequest;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.preprocessResponse;
import static org.springframework.restdocs.operation.preprocess.Preprocessors.prettyPrint;
import static org.springframework.restdocs.payload.PayloadDocumentation.fieldWithPath;
import static org.springframework.restdocs.payload.PayloadDocumentation.requestFields;
import static org.springframework.restdocs.payload.PayloadDocumentation.responseFields;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.backend.auth.dto.LoginRequest;
import com.forever102.backend.auth.dto.LoginResponse;
import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.auth.service.AuthService;
import com.forever102.backend.global.config.SecurityConfig;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.restdocs.test.autoconfigure.AutoConfigureRestDocs;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.restdocs.payload.JsonFieldType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(AuthController.class)
@Import(SecurityConfig.class)
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

    private static final String LOGIN_URL = "/auth/login";
    private static final String VALID_LOGIN_REQUEST = """
            {
              "email": "test@example.com",
              "password": "password123!"
            }
            """;

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AuthService authService;

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
                                        .description("비밀번호. 필수, 10~128자, 영문·숫자·특수문자를 모두 포함."),
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
    @DisplayName("비밀번호가 10자 미만이면 400으로 응답한다")
    void signUpRejectsShortPassword() throws Exception {
        // given
        String request = """
                {
                  "email": "test@example.com",
                  "password": "pw12345!",
                  "nickname": "trenduser"
                }
                """;

        // when & then
        mockMvc.perform(post(SIGN_UP_URL)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(request))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("비밀번호는 10자 이상 128자 이하여야 합니다."));
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
}
