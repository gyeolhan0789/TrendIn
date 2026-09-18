"""ISO 3166-1 alpha-2 국가 코드 목록. **소스를 등록할 때 국가 오기를 막는다.**

`SourceDef.country` 와 소스 프로필의 `country` 가 이 목록을 통과해야 한다. 모양만 보는
검사(`[A-Z]{2}`)로는 `UK` 나 `EN` 이 그대로 지나간다 — 둘 다 실재하지 않는 코드이고,
영국의 코드는 `GB` 다.

**오기가 조용한 이유는 나라 이름을 우리가 만들지 않기 때문이다.** 백엔드는 코드만 저장하고
화면에 띄울 이름을 `Locale.of("", code).getDisplayCountry(KOREAN)` 로 얻는데, 목록에 없는
코드는 이름 대신 코드가 그대로 나온다. 실측하면 `GB` 는 "영국", `UK` 는 "UK" 다. 그러니
잘못 등록된 나라는 화면에 가서야 드러나고, 그때는 원자료와 지표에 이미 퍼져 있다.

**그래서 이 목록의 출처가 자바다.** 백엔드가 이름을 만들 때 쓰는 바로 그 목록
(`java.util.Locale.getISOCountries()`, JDK 17, 249개)을 그대로 박아 두었다. 다른 출처를 쓰면
우리가 통과시킨 코드를 백엔드가 모르는 경우가 생긴다 — 예를 들어 `babel` 의 지역 목록은
258개이고 `EU`·`ZZ` 처럼 나라가 아닌 것을 포함한다.

**라이브러리를 의존으로 더하지 않는 이유**는 필요한 것이 이름이 아니라 "실재하는 코드인가"
하나뿐이기 때문이다. ISO 코드는 거의 바뀌지 않으므로 목록을 들고 있는 비용이 낮다. 바뀌면
위 자바 한 줄을 다시 돌려 갱신하고, 그때 `tests/common/test_iso3166.py` 의 개수도 함께
고친다.

⚠️ **판정 불가(`XX`)는 여기 없다.** ISO 가 사용자 지정 영역으로 비워 둔 자리라서 목록에
들어갈 수 없고, 그 값을 받는 것은 `contracts.UNKNOWN_COUNTRY` 쪽 규약이다.
"""

from __future__ import annotations

# `java.util.Locale.getISOCountries()` (JDK 17) 에서 뽑았다. 2026-09-18 기준 249개.
ISO_3166_1_ALPHA_2: frozenset[str] = frozenset((
    "AD", "AE", "AF", "AG", "AI", "AL", "AM", "AO", "AQ", "AR",
    "AS", "AT", "AU", "AW", "AX", "AZ", "BA", "BB", "BD", "BE",
    "BF", "BG", "BH", "BI", "BJ", "BL", "BM", "BN", "BO", "BQ",
    "BR", "BS", "BT", "BV", "BW", "BY", "BZ", "CA", "CC", "CD",
    "CF", "CG", "CH", "CI", "CK", "CL", "CM", "CN", "CO", "CR",
    "CU", "CV", "CW", "CX", "CY", "CZ", "DE", "DJ", "DK", "DM",
    "DO", "DZ", "EC", "EE", "EG", "EH", "ER", "ES", "ET", "FI",
    "FJ", "FK", "FM", "FO", "FR", "GA", "GB", "GD", "GE", "GF",
    "GG", "GH", "GI", "GL", "GM", "GN", "GP", "GQ", "GR", "GS",
    "GT", "GU", "GW", "GY", "HK", "HM", "HN", "HR", "HT", "HU",
    "ID", "IE", "IL", "IM", "IN", "IO", "IQ", "IR", "IS", "IT",
    "JE", "JM", "JO", "JP", "KE", "KG", "KH", "KI", "KM", "KN",
    "KP", "KR", "KW", "KY", "KZ", "LA", "LB", "LC", "LI", "LK",
    "LR", "LS", "LT", "LU", "LV", "LY", "MA", "MC", "MD", "ME",
    "MF", "MG", "MH", "MK", "ML", "MM", "MN", "MO", "MP", "MQ",
    "MR", "MS", "MT", "MU", "MV", "MW", "MX", "MY", "MZ", "NA",
    "NC", "NE", "NF", "NG", "NI", "NL", "NO", "NP", "NR", "NU",
    "NZ", "OM", "PA", "PE", "PF", "PG", "PH", "PK", "PL", "PM",
    "PN", "PR", "PS", "PT", "PW", "PY", "QA", "RE", "RO", "RS",
    "RU", "RW", "SA", "SB", "SC", "SD", "SE", "SG", "SH", "SI",
    "SJ", "SK", "SL", "SM", "SN", "SO", "SR", "SS", "ST", "SV",
    "SX", "SY", "SZ", "TC", "TD", "TF", "TG", "TH", "TJ", "TK",
    "TL", "TM", "TN", "TO", "TR", "TT", "TV", "TW", "TZ", "UA",
    "UG", "UM", "US", "UY", "UZ", "VA", "VC", "VE", "VG", "VI",
    "VN", "VU", "WF", "WS", "YE", "YT", "ZA", "ZM", "ZW",
))


def is_known_country(code: str) -> bool:
    """실재하는 ISO 3166-1 alpha-2 코드인가. 판정 불가(`XX`)는 여기서 거짓이다."""
    return code in ISO_3166_1_ALPHA_2
