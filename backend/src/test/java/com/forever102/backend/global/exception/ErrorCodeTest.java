package com.forever102.backend.global.exception;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.stream.Stream;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.http.HttpStatus;

class ErrorCodeTest {

    @ParameterizedTest(name = "{0}")
    @MethodSource("errorCodeAndStatus")
    @DisplayName("각 ErrorCode는 정의된 HTTP 상태 코드를 가진다")
    void errorCodeHasDefinedStatus(ErrorCode errorCode, HttpStatus status) {
        // given & when & then
        assertThat(errorCode.getStatus()).isEqualTo(status);
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("errorCodeAndMessage")
    @DisplayName("각 ErrorCode는 정의된 안내 메시지를 가진다")
    void errorCodeHasDefinedMessage(ErrorCode errorCode, String message) {
        // given & when & then
        assertThat(errorCode.getMessage()).isEqualTo(message);
    }

    @ParameterizedTest
    @EnumSource(ErrorCode.class)
    @DisplayName("모든 ErrorCode는 클라이언트에 내려줄 메시지를 비워두지 않는다")
    void everyErrorCodeHasMessage(ErrorCode errorCode) {
        // given & when & then
        assertThat(errorCode.getMessage()).isNotBlank();
    }

    static Stream<Arguments> errorCodeAndStatus() {
        return Stream.of(
                Arguments.of(ErrorCode.VALIDATION_ERROR, HttpStatus.BAD_REQUEST),
                Arguments.of(ErrorCode.EMAIL_ALREADY_EXISTS, HttpStatus.CONFLICT),
                Arguments.of(ErrorCode.INTERNAL_SERVER_ERROR, HttpStatus.INTERNAL_SERVER_ERROR)
        );
    }

    static Stream<Arguments> errorCodeAndMessage() {
        return Stream.of(
                Arguments.of(ErrorCode.VALIDATION_ERROR, "입력값이 올바르지 않습니다."),
                Arguments.of(ErrorCode.EMAIL_ALREADY_EXISTS, "이미 가입된 이메일입니다."),
                Arguments.of(ErrorCode.INTERNAL_SERVER_ERROR, "서버에 오류가 발생했습니다.")
        );
    }
}
