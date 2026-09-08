package com.forever102.global.response;

import static org.assertj.core.api.Assertions.assertThat;

import com.forever102.global.exception.ErrorCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;

class ErrorResponseTest {

    @Test
    @DisplayName("에러 응답은 전달한 메시지를 담는다")
    void errorResponseHoldsMessage() {
        // given
        String message = "에러 메시지";

        // when
        ErrorResponse response = ErrorResponse.of(message);

        // then
        assertThat(response.message()).isEqualTo("에러 메시지");
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {"에러 메시지"})
    @DisplayName("에러 응답의 success는 메시지와 무관하게 항상 false다")
    void errorResponseIsAlwaysFail(String message) {
        // given & when
        ErrorResponse response = ErrorResponse.of(message);

        // then
        assertThat(response.success()).isFalse();
    }

    @Test
    @DisplayName("ErrorCode의 메시지로도 에러 응답을 만들 수 있다")
    void errorResponseHoldsErrorCodeMessage() {
        // given
        ErrorCode errorCode = ErrorCode.INTERNAL_SERVER_ERROR;

        // when
        ErrorResponse response = ErrorResponse.of(errorCode.getMessage());

        // then
        assertThat(response).isEqualTo(new ErrorResponse(false, "서버에 오류가 발생했습니다."));
    }

    @Test
    @DisplayName("메시지가 같은 두 에러 응답은 서로 같다")
    void errorResponsesWithSameMessageAreEqual() {
        // given
        ErrorResponse response = ErrorResponse.of("에러 메시지");

        // when
        ErrorResponse other = ErrorResponse.of("에러 메시지");

        // then
        assertThat(response).isEqualTo(other);
    }

    @Test
    @DisplayName("메시지가 다른 두 에러 응답은 서로 다르다")
    void errorResponsesWithDifferentMessageAreNotEqual() {
        // given
        ErrorResponse response = ErrorResponse.of("에러 메시지");

        // when
        ErrorResponse other = ErrorResponse.of("다른 메시지");

        // then
        assertThat(response).isNotEqualTo(other);
    }
}
