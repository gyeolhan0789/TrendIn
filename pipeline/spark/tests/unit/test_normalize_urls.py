"""URL 정규화 ([03 §6]). SparkSession 없이 검사한다 ([09 §4] 층 1).

**이 모듈의 출력이 곧 유일성 기준이다** — `contents.url` 에 UNIQUE 가 직접 걸려 있고
중복 제거 2단계가 `url_hash` 로 대표를 고른다. 그래서 여기 테스트는 "규칙이 이것이다" 를
고정하는 것이 목적이다. 규칙을 바꾸면 이 파일이 먼저 깨져야 한다.
"""

from __future__ import annotations

import pytest

from trendin.spark.normalize.urls import URL_MAX_BYTES, normalize_url, too_long, url_hash


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 스킴·호스트 소문자
        ("HTTPS://WWW.Vogue.CO.KR/a", "https://www.vogue.co.kr/a"),
        # 기본 포트 제거. 기본이 아닌 포트는 남는다
        ("https://a.com:443/x", "https://a.com/x"),
        ("http://a.com:80/x", "http://a.com/x"),
        ("https://a.com:8443/x", "https://a.com:8443/x"),
        # 프래그먼트는 서버에 전달되지 않으므로 다른 문서일 수 없다
        ("https://a.com/x#section", "https://a.com/x"),
        # 후행 슬래시 정리. 루트는 "/" 로 남는다 — 빈 경로와 가르면 같은 문서가 둘이 된다
        ("https://a.com/x/", "https://a.com/x"),
        ("https://a.com/", "https://a.com/"),
        ("https://a.com", "https://a.com/"),
        # 질의 키 정렬 — 소스가 목록 페이지마다 순서를 바꿔 내는 일이 있다
        ("https://a.com/x?b=2&a=1", "https://a.com/x?a=1&b=2"),
    ],
)
def test_정규화_규칙(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "tracking",
    ["utm_source=x", "utm_medium=y", "fbclid=z", "gclid=z", "ref=nav", "source=rss"],
)
def test_추적_파라미터는_지워진다(tracking):
    """지우지 않으면 같은 기사가 유입 경로마다 다른 `contents` 행이 된다."""
    assert normalize_url(f"https://a.com/x?{tracking}") == "https://a.com/x"


def test_추적이_아닌_파라미터는_남는다():
    """기사 식별에 쓰이는 파라미터가 있다 — 두산 계열의 `?p=854414` 가 그것이다."""
    assert normalize_url("https://a.com/?p=854414&utm_source=x") == "https://a.com/?p=854414"


def test_빈_값_파라미터를_지우지_않는다():
    """`?page=` 가 소스에서 의미를 갖는 경우가 있다. 지우면 다른 URL 이 같은 값으로 접힌다."""
    assert normalize_url("https://a.com/x?page=") == "https://a.com/x?page"


def test_이미_인코딩된_값을_다시_인코딩하지_않는다():
    """`urlencode` 를 쓰면 `%2F` 가 `%252F` 가 되어 원본과 다른 URL 이 된다."""
    assert normalize_url("https://a.com/x?q=a%2Fb") == "https://a.com/x?q=a/b"


def test_자격은_정체성에_넣지_않는다():
    """같은 문서가 자격에 따라 여러 행이 되고, 비밀이 `contents.url` 로 새어 나간다."""
    assert normalize_url("https://user:pw@a.com/x") == "https://a.com/x"


@pytest.mark.parametrize("raw", [None, "", "   ", "/relative/path", "not a url", "mailto:a@b.c"])
def test_정체성을_만들_수_없으면_None(raw):
    """**`None` 이 정상 경로다.** 예외를 올리면 그 한 건이 배치를 죽인다.

    거른 건수는 [03 §7] 이 `NO_URL` 로 센다.
    """
    assert normalize_url(raw) is None


def test_해시는_정규화된_URL_에서_나온다():
    """원본을 넣으면 같은 문서가 다른 해시를 갖는다."""
    left = normalize_url("HTTPS://A.com/x/?utm_source=q")
    right = normalize_url("https://a.com/x")

    assert left == right
    assert url_hash(left) == url_hash(right)
    assert len(url_hash(left)) == 32


def test_해시_입력이_None_이면_None():
    assert url_hash(None) is None


def test_길이는_문자가_아니라_바이트로_센다():
    """한글이 섞인 URL 은 문자 하나가 3바이트다. 문자 수로 재면 통과하고 삽입에서 죽는다."""
    hangul = "https://a.com/" + "가" * ((URL_MAX_BYTES // 3) + 10)

    assert len(hangul) < URL_MAX_BYTES  # 문자 수로는 상한 아래
    assert too_long(hangul)  # 바이트로는 넘는다


@pytest.mark.parametrize("value", [None, "https://a.com/x"])
def test_짧은_URL_은_통과한다(value):
    assert not too_long(value)
