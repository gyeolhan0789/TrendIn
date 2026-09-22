package com.forever102.trend.domain;

import java.util.Locale;

/**
 * 나라 코드를 한국어 이름으로 바꿉니다.
 *
 * 나라별 조회가 여럿이라 각자 이름을 지으면 한 화면 안에서 같은 나라가 다르게 불릴 수 있습니다.
 * 아는 나라가 아니면 Locale 이 코드를 그대로 돌려주므로, 파이프라인이 넣는 XX 도 그대로 나갑니다.
 */
public final class CountryNames {

    private CountryNames() {
    }

    public static String of(String countryCode) {
        return Locale.of("", countryCode).getDisplayCountry(Locale.KOREAN);
    }
}
