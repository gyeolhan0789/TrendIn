"""국가 코드 목록 검사 (`collect/iso3166.py` · `contracts.check_country`).

여기서 막는 것은 **소스를 등록할 때의 오타**다. 모양만 보던 때는 `UK` 가 세 층을 다 통과해
화면에 이름 없이 "UK" 로 나왔고, 그때는 이미 원자료와 지표에 그 값이 퍼져 있었다.
"""

from __future__ import annotations

import pytest

from trendin.common.collect.contracts import UNKNOWN_COUNTRY, SourceDef, check_country
from trendin.common.collect.iso3166 import ISO_3166_1_ALPHA_2, is_known_country


def source(country: str) -> SourceDef:
    return SourceDef(
        key="t",
        domain="fashion",
        route="rss",
        discover_url="https://example.test/feed",
        allowed_url_prefixes=("https://example.test/",),
        country=country,
    )


def test_목록의_출처가_백엔드와_같다():
    """`java.util.Locale.getISOCountries()` (JDK 17) 가 249개다.

    다른 출처를 쓰면 우리가 통과시킨 코드를 백엔드가 몰라 화면에 이름이 안 나온다.
    갱신했다면 이 수를 함께 고친다.
    """
    assert len(ISO_3166_1_ALPHA_2) == 249


def test_실재하지_않는_코드를_거절한다():
    """`UK` 는 흔한 오기다. 영국의 코드는 `GB` 다."""
    for code in ("UK", "EN", "ZZ", "QQ"):
        with pytest.raises(ValueError, match="실재하지 않는 코드"):
            check_country(code, where="시험")


def test_소문자를_받아_올리지_않는다():
    """받아 올리면 프로필마다 표기가 갈리고, 그 값이 원자료 기본키에 들어가 행이 둘이 된다."""
    with pytest.raises(ValueError):
        check_country("kr", where="시험")


def test_판정_불가는_목록_밖이지만_받는다():
    """ISO 가 사용자 지정 영역으로 비워 둔 자리라 목록에 들어갈 수 없다."""
    assert not is_known_country(UNKNOWN_COUNTRY)
    assert check_country(UNKNOWN_COUNTRY, where="시험") == UNKNOWN_COUNTRY


def test_어느_소스인지가_메시지에_있다():
    """목록에 없는 코드는 대개 오타라, 어느 소스인지 알아야 바로 고칠 수 있다."""
    with pytest.raises(ValueError, match="vogue.toml"):
        check_country("UK", where="vogue.toml")


def test_코드로_직접_적은_소스도_막힌다():
    """목록 소스와 API 소스는 프로필 로더를 지나지 않는다.

    검사가 로더에만 있으면 그쪽으로 오기가 들어온다.
    """
    with pytest.raises(ValueError, match="실재하지 않는 코드"):
        source("UK")

    assert source("GB").country == "GB"
    assert source(UNKNOWN_COUNTRY).country == UNKNOWN_COUNTRY


def test_지금_등록된_소스가_전부_통과한다():
    """검사를 넣은 것이 기존 등록을 깨지 않는지 본다."""
    from trendin.dev.collect import sources as dev
    from trendin.fashion.collect import sources as fashion

    for registry in (fashion.BY_KEY, dev.BY_KEY):
        for key, definition in registry.items():
            assert check_country(definition.country, where=key) == definition.country
