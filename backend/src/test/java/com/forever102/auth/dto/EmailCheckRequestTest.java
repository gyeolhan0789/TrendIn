package com.forever102.auth.dto;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class EmailCheckRequestTest {

    @Test
    @DisplayName("이메일은 소문자로 정규화된다")
    void normalizesEmailToLowerCase() {
        // given
        String email = "Test@Example.COM";

        // when
        EmailCheckRequest request = new EmailCheckRequest(email);

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("이메일의 앞뒤 공백은 제거된다")
    void stripsEmail() {
        // given
        String email = "  test@example.com  ";

        // when
        EmailCheckRequest request = new EmailCheckRequest(email);

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("이메일이 null이어도 정규화 과정에서 예외가 발생하지 않는다")
    void allowsNullEmail() {
        // given & when
        EmailCheckRequest request = new EmailCheckRequest(null);

        // then
        assertThat(request.email()).isNull();
    }

    @Test
    @DisplayName("회원가입 요청과 같은 값으로 정규화되어 확인 결과와 가입 결과가 어긋나지 않는다")
    void normalizesSameWayAsSignUpRequest() {
        // given
        String email = "  Test@Example.COM  ";

        // when
        EmailCheckRequest checkRequest = new EmailCheckRequest(email);
        SignUpRequest signUpRequest = new SignUpRequest(email, "password123!", "trenduser");

        // then
        assertThat(checkRequest.email()).isEqualTo(signUpRequest.email());
    }
}
