"""소스 레지스트리 (설계 문서 #1 표)."""

import re

import pytest

from trendin.fashion.collect import sources

ALL_SOURCES = sources.RSS_SOURCES + sources.LISTING_SOURCES


def test_등록한_소스_목록이다():
    assert sorted(sources.BY_KEY) == [
        "allure",
        "cosmopolitan",
        "dazed",
        "elle_cn",
        "elle_it",
        "elle_us",
        "glamour_uk",
        "globenewswire",
        "gq_us",
        "gqkorea",
        "harpersbazaar",
        "harpersbazaar_us",
        "highsnobiety",
        "hypebeast",
        "id",
        "iodonna",
        "luxe_co",
        "marieclaire",
        "marieclaire_uk",
        "prnewswire",
        "theindustry",
        "vogue",
        "vogue_it",
        "vogue_uk",
        "vogue_us",
        "whowhatwear",
        "wkorea",
    ]


def test_한_레지스트리가_두_route_를_다_찾는다():
    """route 를 먼저 알아야 정의를 찾을 수 있으면 probe 와 167 이 각자 표를 든다."""
    assert sources.get("vogue").route == "rss"
    assert sources.get("harpersbazaar").route == "listing"


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.key)
def test_발견_URL_이_허용_범위_안에_있다(source):
    assert source.allowed_url_prefixes
    assert source.discover_url.startswith(source.allowed_url_prefixes)


@pytest.mark.parametrize("source", sources.RSS_SOURCES, ids=lambda s: s.key)
def test_피드_소스는_route_와_도메인이_고정이다(source):
    assert source.route == "rss"
    assert source.domain == "fashion"
    assert source.listing_sections == ()


@pytest.mark.parametrize("source", sources.LISTING_SOURCES, ids=lambda s: s.key)
def test_목록_소스는_하위_섹션_다섯을_가진다(source):
    """Jira 164 경계가 섹션을 명시한다. 루트까지 여섯 장을 돈다."""
    assert source.route == "listing"
    assert source.domain == "fashion"
    assert len(source.listing_sections) == 5
    for slug in source.listing_sections:
        assert f"{source.discover_url}/{slug}".startswith(source.allowed_url_prefixes)


def test_국가는_발행_법인의_소재지다():
    """국가는 본사가 아니라 **발행 법인의 소재지**다 (설계 문서 #3.2 운영 법인 표).

    Vogue 와 Harper's Bazaar 는 본사가 미국이지만 두산매거진과 허스트중앙(유) 가 한국에서
    발행하므로 `KR` 이다. 이 시험이 지키는 것은 값 목록이 아니라 그 기준이다 — 본사
    기준으로 되돌리면 두 소스가 `US` 로 바뀌면서 여기서 걸린다.
    """
    assert {key: source.country for key, source in sources.BY_KEY.items()} == {
        "vogue": "KR",
        "gqkorea": "KR",
        "wkorea": "KR",
        "allure": "KR",
        "marieclaire": "KR",
        "harpersbazaar": "KR",
        "cosmopolitan": "KR",
        "hypebeast": "HK",
        "glamour_uk": "GB",
        "marieclaire_uk": "GB",
        "dazed": "GB",
        "vogue_uk": "GB",
        "id": "GB",
        "theindustry": "GB",
        "vogue_it": "IT",
        "iodonna": "IT",
        "elle_it": "IT",
        "vogue_us": "US",
        "gq_us": "US",
        "harpersbazaar_us": "US",
        "elle_us": "US",
        "whowhatwear": "US",
        "prnewswire": "US",
        "globenewswire": "US",
        "elle_cn": "CN",
        "luxe_co": "CN",
        "highsnobiety": "DE",
    }


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.key)
def test_국가는_대문자_두_글자다(source):
    """ISO 3166-1 alpha-2 대문자. 소문자나 세 글자를 섞으면 소비 측이 같은 나라를 둘로 센다."""
    assert re.fullmatch(r"[A-Z]{2}", source.country), source.country


def test_모르는_소스는_있는_것을_알려주며_실패한다():
    with pytest.raises(KeyError, match="vogue"):
        sources.get("nosuchsource")
