package com.forever102.backend.auth.dto;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class LoginRequestTest {

    @Test
    @DisplayName("이메일은 소문자로 정규화된다")
    void normalizesEmailToLowerCase() {
        // given
        String email = "Test@Example.COM";

        // when
        LoginRequest request = new LoginRequest(email, "password123!");

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("이메일의 앞뒤 공백은 제거된다")
    void stripsEmail() {
        // given
        String email = "  test@example.com  ";

        // when
        LoginRequest request = new LoginRequest(email, "password123!");

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("이메일이 null이어도 정규화 과정에서 예외가 발생하지 않는다")
    void allowsNullEmail() {
        // given & when
        LoginRequest request = new LoginRequest(null, "password123!");

        // then
        assertThat(request.email()).isNull();
    }

    @Test
    @DisplayName("비밀번호는 정규화하지 않고 그대로 보관한다")
    void keepsPasswordAsIs() {
        // given
        String password = "  Password123!  ";

        // when
        LoginRequest request = new LoginRequest("test@example.com", password);

        // then
        assertThat(request.password()).isEqualTo("  Password123!  ");
    }
}
