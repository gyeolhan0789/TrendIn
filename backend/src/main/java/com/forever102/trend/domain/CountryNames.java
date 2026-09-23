package com.forever102.trend.domain;

import java.util.Locale;
import java.util.regex.Pattern;

/**
 * 나라 코드를 한국어 이름으로 바꿉니다.
 *
 * 나라별 조회가 여럿이라 각자 이름을 지으면 한 화면 안에서 같은 나라가 다르게 불릴 수 있습니다.
 * 아는 나라가 아니면 Locale 이 코드를 그대로 돌려주므로, 파이프라인이 넣는 XX 도 그대로 나갑니다.
 */
public final class CountryNames {

    /*
     * Locale 은 홍콩·마카오에 지위를 괄호로 덧붙입니다("홍콩(중국 특별행정구)"). 좁은 목록 칸에서
     * 이름보다 괄호가 길어 떼어 냅니다. JDK 25 기준으로 괄호가 붙는 코드는 HK·MO 둘뿐입니다.
     */
    private static final Pattern QUALIFIER = Pattern.compile("\\s*\\([^)]*\\)$");

    private CountryNames() {
    }

    public static String of(String countryCode) {
        String name = Locale.of("", countryCode).getDisplayCountry(Locale.KOREAN);
        return QUALIFIER.matcher(name).replaceFirst("");
    }
}
