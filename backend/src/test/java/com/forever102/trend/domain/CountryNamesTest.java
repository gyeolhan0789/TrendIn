package com.forever102.trend.domain;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class CountryNamesTest {

    @ParameterizedTest
    @CsvSource({"KR,대한민국", "JP,일본", "HK,홍콩", "MO,마카오", "XX,XX"})
    @DisplayName("나라 코드를 괄호 없는 한국어 이름으로 바꾸고, 모르는 코드는 그대로 둔다")
    void namesCountryWithoutQualifier(String countryCode, String expected) {
        // when & then
        assertThat(CountryNames.of(countryCode)).isEqualTo(expected);
    }
}
