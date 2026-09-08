package com.forever102.global.exception;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

class BusinessExceptionTest {

    @ParameterizedTest
    @EnumSource(ErrorCode.class)
    @DisplayName("비즈니스 예외는 생성 시 전달받은 ErrorCode를 그대로 보관한다")
    void businessExceptionHoldsErrorCode(ErrorCode errorCode) {
        // given & when
        BusinessException exception = new BusinessException(errorCode);

        // then
        assertThat(exception.getErrorCode()).isSameAs(errorCode);
    }

    @ParameterizedTest
    @EnumSource(ErrorCode.class)
    @DisplayName("비즈니스 예외의 메시지는 ErrorCode의 메시지와 같다")
    void businessExceptionUsesErrorCodeMessage(ErrorCode errorCode) {
        // given & when
        BusinessException exception = new BusinessException(errorCode);

        // then
        assertThat(exception.getMessage()).isEqualTo(errorCode.getMessage());
    }

    @Test
    @DisplayName("비즈니스 예외는 별도의 선언 없이 던질 수 있는 언체크 예외다")
    void businessExceptionIsUnchecked() {
        // given
        ErrorCode errorCode = ErrorCode.INTERNAL_SERVER_ERROR;

        // when & then
        assertThatThrownBy(() -> {
            throw new BusinessException(errorCode);
        })
                .isInstanceOf(RuntimeException.class)
                .hasMessage("서버에 오류가 발생했습니다.");
    }
}
