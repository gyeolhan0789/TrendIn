"""기사 페이지 본문 추출 (설계 문서 확정 2, S15P21A102-285).

`tests/fixtures/articles/` 는 2026-09-17 에 후보 소스의 피드에서 첫 기사를 받아 그대로
gzip 한 것이다(자르지 않았다). 파일 이름은 `{소스 키}__{피드에서의 순번}[_paywalled]` 다.
소스당 무료 기사 한 장, 유료 표시가 붙은 기사가 나오면 그것도 한 장이다.

아래 표는 **지금 코드가 그 페이지에서 내는 결과**다. trafilatura 를 2.2.0 으로 고정한 것이
이 표를 고정값으로 쓸 수 있는 근거다(`pyproject.toml`). 값이 바뀌면 추출 규칙이나 버전이
바뀐 것이고, 그 diff 가 리뷰 근거다.

`fashionista` · `wwdjapan` 은 기사 페이지가 403 이라 받지 않았다(불변식 2). BoF · Drapers ·
WWD · note · Harper's Bazaar US · Substack 은 받은 기사가 전부 유료 표시라 무료 기사 표본이
없다 — 이 여섯 곳의 무료 기사 추출은 S15P21A102-291 에서 다시 잰다.
"""

import gzip
import pathlib

import pytest

from trendin.common.collect.body import (
    decode_page,
    extract_body,
    find_ld_articles,
    is_paywalled,
    ld_body_fragment,
)
from trendin.common.collect.html_text import text_length

ARTICLES = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "articles"

# 파일 이름 → (유료 표시, 본문을 얻은 경로, 본문 글자 수)
EXPECTED = {
    "allure__0.html.gz": (False, "ld_json", 528),
    "ameba__0.html.gz": (False, "trafilatura", 1039),
    "bof__0_paywalled.html.gz": (True, None, 0),
    "cancam__0.html.gz": (False, "trafilatura", 1128),
    "dazed__0.html.gz": (False, "trafilatura", 8355),
    "drapers__0_paywalled.html.gz": (True, None, 0),
    "elle_cn__0.html.gz": (False, "ld_json", 1722),
    "elle_it__0.html.gz": (False, "ld_json", 5829),
    "elle_us__0_paywalled.html.gz": (True, None, 0),
    "elle_us__1.html.gz": (False, "ld_json", 546),
    "fashionsnap__0.html.gz": (False, "trafilatura", 464),
    "figaro_jp__0.html.gz": (False, "trafilatura", 1671),
    "fudge__0.html.gz": (False, "trafilatura", 1195),
    "glamour_uk__0.html.gz": (False, "ld_json", 6198),
    "globenewswire__0.html.gz": (False, "trafilatura", 3911),
    "gq_us__0.html.gz": (False, "ld_json", 11355),
    "gqkorea__0.html.gz": (False, "trafilatura", 3396),
    "grazia_it__0.html.gz": (False, "trafilatura", 2733),
    "harpersbazaar_us__0_paywalled.html.gz": (True, None, 0),
    "hatena__0.html.gz": (False, "trafilatura", 709),
    "highsnobiety__0.html.gz": (False, "trafilatura", 1136),
    "houyhnhnm__0.html.gz": (False, "trafilatura", 849),
    "id__0.html.gz": (False, "trafilatura", 4723),
    "iodonna__0.html.gz": (False, "trafilatura", 2940),
    "itnk__0.html.gz": (False, "trafilatura", 993),
    "journaldutextile__0.html.gz": (False, "trafilatura", 6536),
    "ktnews__0.html.gz": (False, "trafilatura", 635),
    "lofficiel__0.html.gz": (False, "trafilatura", 368),
    "luxe_co__0.html.gz": (False, "trafilatura", 508),
    "marieclaire__0.html.gz": (False, "ld_json", 1813),
    "marieclaire_uk__0.html.gz": (False, "trafilatura", 4660),
    "mensnonno__0.html.gz": (False, "trafilatura", 752),
    "note_mb__0_paywalled.html.gz": (True, None, 0),
    "numero__0.html.gz": (False, "trafilatura", 5513),
    "oggi__0.html.gz": (False, "trafilatura", 2951),
    "pambianco__0.html.gz": (False, "trafilatura", 3720),
    "prnewswire__0.html.gz": (False, "trafilatura", 4207),
    "prtimes__0.html.gz": (False, "trafilatura", 2902),
    "senken__0.html.gz": (False, "trafilatura", 639),
    "substack_bbsp__0_paywalled.html.gz": (True, None, 0),
    "theindustry__0.html.gz": (False, "trafilatura", 2491),
    "vogue__0.html.gz": (False, "trafilatura", 508),
    "vogue_fr__0.html.gz": (False, "ld_json", 1654),
    "vogue_it__0.html.gz": (False, "ld_json", 4558),
    "vogue_jp__0.html.gz": (False, "ld_json", 909),
    "vogue_uk__0.html.gz": (False, "ld_json", 1155),
    "vogue_us__0.html.gz": (False, "ld_json", 18050),
    "whowhatwear__0.html.gz": (False, "trafilatura", 5376),
    "wkorea__0.html.gz": (False, "trafilatura", 827),
    "wwd__0_paywalled.html.gz": (True, None, 0),
}

# 완료 기준이 소스 이름으로 못 박은 두 무리 (Jira S15P21A102-285).
LD_SOURCES = {"vogue_us", "vogue_uk", "vogue_jp", "vogue_fr", "vogue_it", "gq_us", "glamour_uk"}
TRAFILATURA_SOURCES = {
    "dazed",
    "fashionsnap",
    "senken",
    "prtimes",
    "journaldutextile",
    "prnewswire",
    "globenewswire",
    "ktnews",
    "itnk",
}


def page(name: str) -> str:
    return decode_page(gzip.decompress((ARTICLES / name).read_bytes()))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_실측_기사_페이지에서_본문이_나온다(name):
    result = extract_body(page(name))
    paywalled, via, length = EXPECTED[name]
    assert (result.paywalled, result.via, text_length(result.body_text or "")) == (
        paywalled,
        via,
        length,
    )
    assert name.endswith("_paywalled.html.gz") is paywalled


def test_받은_파일이_표와_같다():
    """표에 없는 파일을 넣거나 파일을 지우면 여기서 걸린다."""
    assert {f.name for f in ARTICLES.glob("*.html.gz")} == set(EXPECTED)


@pytest.mark.parametrize("group", ["ld", "trafilatura"])
def test_완료_기준의_두_무리가_각자의_경로로_나온다(group):
    wanted = LD_SOURCES if group == "ld" else TRAFILATURA_SOURCES
    via = "ld_json" if group == "ld" else "trafilatura"
    seen = {
        name.split("__")[0]: EXPECTED[name][1]
        for name in EXPECTED
        if name.split("__")[0] in wanted and not EXPECTED[name][0]
    }
    assert set(seen) == wanted
    assert set(seen.values()) == {via}


def test_유료_표시_기사는_본문을_만들지_않는다():
    """HTML 에 본문이 실려 와도 같다 (불변식 2). WWD 는 기사 노드가 둘인데 뒤쪽만 유료다."""
    wwd = page("wwd__0_paywalled.html.gz")
    nodes = find_ld_articles(wwd)
    assert len(nodes) == 2 and nodes[0].get("isAccessibleForFree") is None
    assert is_paywalled(nodes) is True
    assert extract_body(wwd).body_text is None


def test_피드_본문이_더_길면_피드_본문을_쓴다():
    """전문 피드에서 페이지 추출이 짧아지는 일이 있다 (L'Officiel 2,902자 → 368자)."""
    html = page("lofficiel__0.html.gz")
    long_feed = "<p>" + "가나다라마바사" * 100 + "</p>"
    assert extract_body(html, feed_body=long_feed).via == "feed"
    assert extract_body(html, feed_body="<p>짧다</p>").via == "trafilatura"


def test_ld_json_본문이_티저면_trafilatura_로_넘어간다():
    """WWD 의 articleBody 는 66자, 같은 페이지의 trafilatura 추출은 3,830자다."""
    nodes = find_ld_articles(page("wwd__0_paywalled.html.gz"))
    assert 0 < text_length(ld_body_fragment(nodes)) < 100


def test_ld_json_본문은_문단마다_p_로_감싸고_이스케이프한다():
    nodes = [{"@type": "NewsArticle", "articleBody": "영화 <문라이트> & 끝.\n둘째 줄."}]
    assert ld_body_fragment(nodes) == "<p>영화 &lt;문라이트&gt; &amp; 끝.</p><p>둘째 줄.</p>"


def test_ld_json_이_없는_페이지도_추출한다():
    assert find_ld_articles(page("senken__0.html.gz")) == []
    assert extract_body(page("senken__0.html.gz")).via == "trafilatura"
