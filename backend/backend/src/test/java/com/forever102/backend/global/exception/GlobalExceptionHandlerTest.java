package com.forever102.backend.global.exception;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.forever102.backend.global.response.ErrorResponse;
import java.lang.reflect.Method;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.BeanPropertyBindingResult;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.validation.ObjectError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

class GlobalExceptionHandlerTest {

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new TestController())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Nested
    @DisplayName("비즈니스 예외가 발생하면")
    class WhenBusinessExceptionThrown {

        @Test
        @DisplayName("ErrorCode에 정의된 HTTP 상태 코드로 응답한다")
        void respondsWithErrorCodeStatus() throws Exception {
            // given & when
            var result = mockMvc.perform(get("/tests/validation-error"));

            // then
            result.andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("ErrorCode마다 서로 다른 HTTP 상태 코드로 응답한다")
        void respondsWithStatusOfEachErrorCode() throws Exception {
            // given & when
            var result = mockMvc.perform(get("/tests/server-error"));

            // then
            result.andExpect(status().isInternalServerError());
        }

        @Test
        @DisplayName("실패를 알리는 에러 응답 본문을 내려준다")
        void respondsWithErrorResponseBody() throws Exception {
            // given & when
            var result = mockMvc.perform(get("/tests/validation-error"));

            // then
            result.andExpect(jsonPath("$.success").value(false))
                    .andExpect(jsonPath("$.message").value("입력값이 올바르지 않습니다."));
        }
    }

    @Nested
    @DisplayName("요청 값 유효성 검증에 실패하면")
    class WhenValidationFailed {

        private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

        @Test
        @DisplayName("400과 함께 실패한 필드의 메시지를 내려준다")
        void respondsWithFieldErrorMessage() throws Exception {
            // given
            MethodArgumentNotValidException exception =
                    validationExceptionWith(new FieldError("testRequest", "name", "이름은 필수입니다."));

            // when
            ResponseEntity<ErrorResponse> response = handler.handleValidationException(exception);

            // then
            assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
            assertThat(response.getBody()).isEqualTo(ErrorResponse.of("이름은 필수입니다."));
        }

        @Test
        @DisplayName("필드 단위 오류가 없으면 기본 유효성 오류 메시지를 내려준다")
        void respondsWithDefaultMessageWhenNoFieldError() throws Exception {
            // given
            MethodArgumentNotValidException exception =
                    validationExceptionWith(new ObjectError("testRequest", "객체 전체가 올바르지 않습니다."));

            // when
            ResponseEntity<ErrorResponse> response = handler.handleValidationException(exception);

            // then
            assertThat(response.getBody())
                    .isEqualTo(ErrorResponse.of(ErrorCode.VALIDATION_ERROR.getMessage()));
        }

        private MethodArgumentNotValidException validationExceptionWith(ObjectError error) throws Exception {
            Method method = TestController.class.getDeclaredMethod("validated", TestRequest.class);
            BindingResult bindingResult = new BeanPropertyBindingResult(new TestRequest(null), "testRequest");
            bindingResult.addError(error);
            return new MethodArgumentNotValidException(new MethodParameter(method, 0), bindingResult);
        }
    }

    @Nested
    @DisplayName("처리되지 않은 예외가 발생하면")
    class WhenUnexpectedExceptionThrown {

        @Test
        @DisplayName("500으로 응답한다")
        void respondsWithInternalServerError() throws Exception {
            // given & when
            var result = mockMvc.perform(get("/tests/unexpected-error"));

            // then
            result.andExpect(status().isInternalServerError());
        }

        @Test
        @DisplayName("내부 예외 메시지 대신 정해진 안내 메시지를 내려준다")
        void doesNotExposeInternalMessage() throws Exception {
            // given & when
            var result = mockMvc.perform(get("/tests/unexpected-error"));

            // then
            result.andExpect(jsonPath("$.success").value(false))
                    .andExpect(jsonPath("$.message").value("서버에 오류가 발생했습니다."));
        }
    }

    record TestRequest(String name) {
    }

    @RestController
    static class TestController {

        @GetMapping("/tests/validation-error")
        String throwValidationBusinessException() {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }

        @GetMapping("/tests/server-error")
        String throwServerBusinessException() {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR);
        }

        @GetMapping("/tests/unexpected-error")
        String throwUnexpectedException() {
            throw new IllegalStateException("DB 커넥션 획득에 실패했습니다.");
        }

        @GetMapping("/tests/validated")
        String validated(TestRequest request) {
            return request.name();
        }
    }
}
