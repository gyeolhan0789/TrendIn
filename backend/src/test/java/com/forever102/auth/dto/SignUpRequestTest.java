package com.forever102.auth.dto;

import static org.assertj.core.api.Assertions.assertThat;

import jakarta.validation.Validation;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class SignUpRequestTest {

    @ParameterizedTest
    @ValueSource(ints = {8, 9, 10, 128})
    @DisplayName("영문·숫자·특수문자를 포함한 8~128자 비밀번호는 허용한다")
    void acceptsPasswordWithinLengthRange(int length) {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var request = new SignUpRequest("test@example.com", "a1!" + "a".repeat(length - 3), "trenduser");
            assertThat(factory.getValidator().validate(request)).isEmpty();
        }
    }

    @ParameterizedTest
    @ValueSource(ints = {7, 129})
    @DisplayName("8자 미만 또는 128자 초과 비밀번호는 거부한다")
    void rejectsPasswordOutsideLengthRange(int length) {
        try (var factory = Validation.buildDefaultValidatorFactory()) {
            var request = new SignUpRequest("test@example.com", "a1!" + "a".repeat(length - 3), "trenduser");
            assertThat(factory.getValidator().validate(request))
                    .anySatisfy(violation -> assertThat(violation.getMessage())
                            .isEqualTo("비밀번호는 8자 이상 128자 이하여야 합니다."));
        }
    }

    @Test
    @DisplayName("이메일은 소문자로 정규화된다")
    void normalizesEmailToLowerCase() {
        // given
        String email = "Test@Example.COM";

        // when
        SignUpRequest request = new SignUpRequest(email, "password123!", "trenduser");

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("이메일의 앞뒤 공백은 제거된다")
    void stripsEmail() {
        // given
        String email = "  test@example.com  ";

        // when
        SignUpRequest request = new SignUpRequest(email, "password123!", "trenduser");

        // then
        assertThat(request.email()).isEqualTo("test@example.com");
    }

    @Test
    @DisplayName("닉네임의 앞뒤 공백은 제거된다")
    void stripsNickname() {
        // given
        String nickname = "  trenduser  ";

        // when
        SignUpRequest request = new SignUpRequest("test@example.com", "password123!", nickname);

        // then
        assertThat(request.nickname()).isEqualTo("trenduser");
    }

    @Test
    @DisplayName("이메일이 null이어도 정규화 과정에서 예외가 발생하지 않는다")
    void allowsNullEmail() {
        // given & when
        SignUpRequest request = new SignUpRequest(null, "password123!", "trenduser");

        // then
        assertThat(request.email()).isNull();
    }

    @Test
    @DisplayName("닉네임이 null이어도 정규화 과정에서 예외가 발생하지 않는다")
    void allowsNullNickname() {
        // given & when
        SignUpRequest request = new SignUpRequest("test@example.com", "password123!", null);

        // then
        assertThat(request.nickname()).isNull();
    }

    @Test
    @DisplayName("비밀번호는 정규화하지 않고 그대로 보관한다")
    void keepsPasswordAsIs() {
        // given
        String password = "  Password123!  ";

        // when
        SignUpRequest request = new SignUpRequest("test@example.com", password, "trenduser");

        // then
        assertThat(request.password()).isEqualTo("  Password123!  ");
    }
}
