package com.forever102.backend.auth.controller;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.backend.auth.dto.SignUpRequest;
import com.forever102.backend.auth.dto.SignUpResponse;
import com.forever102.backend.auth.service.AuthService;
import com.forever102.backend.global.config.SecurityConfig;
import com.forever102.backend.global.exception.BusinessException;
import com.forever102.backend.global.exception.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(AuthController.class)
@Import(SecurityConfig.class)
class AuthControllerTest {

    private static final String SIGN_UP_URL = "/auth/signup";
    private static final String VALID_REQUEST = """
            {
              "email": "test@example.com",
              "password": "password123!",
              "nickname": "trenduser"
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
                .andExpect(jsonPath("$.data.onboardingCompleted").value(false));
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
                .andExpect(jsonPath("$.message").value("이미 가입된 이메일입니다."));
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
                .andExpect(jsonPath("$.message").value("이메일 형식이 올바르지 않습니다."));
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
}
