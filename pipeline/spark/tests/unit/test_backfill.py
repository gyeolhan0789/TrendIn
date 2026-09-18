"""`--source objects` 백필의 순수 함수 ([02 §6] 모드 B). 층 1 ([09 §4]).

MinIO 를 띄우지 않는다 — 여기서 보는 것은 키를 뜯는 규칙과 범위 검사다. 실제 목록 조회는
`io/objects.list_prefixes` · `list_keys` 가 하고 그건 층 3 이다.
"""

from __future__ import annotations

from datetime import date

import pytest

from trendin.spark.common.config import ConfigError
from trendin.spark.common.countries import UNKNOWN_COUNTRY
from trendin.spark.ingest.backfill import _envelope, build_request, parse_day, parse_key

KEY = "fashion/vogue/rss/2026/09/03/854414/article.json"


def test_계약_fixture_의_키를_뜯는다():
    """fixture 가 실제 생산자 규칙(`collect/keys.article_key`)으로 만들어진 경로다."""
    assert parse_key(KEY) == ("fashion", "vogue", "rss", "854414")


def test_article_id_는_키의_마지막_디렉터리다():
    """[02 §6] 3번이 그렇게 정했다. `event_id` 는 `{source}-{article_id}` 규칙으로 만든다."""
    _domain, _source, _route, article_id = parse_key(KEY)

    assert article_id == "854414"


@pytest.mark.parametrize(
    "key",
    [
        # raw 객체는 우리가 읽지 않는다.
        "fashion/vogue/rss/2026/09/03/854414/raw.xml",
        # 단이 모자라거나 남는다.
        "fashion/vogue/rss/2026/09/03/article.json",
        "fashion/vogue/rss/2026/09/03/854414/extra/article.json",
        # verify.sh 가 남기는 흔적 같은 다른 규칙의 객체.
        "_verify/probe.txt",
        "",
    ],
)
def test_규칙에_맞지_않는_키는_건너뛴다(key):
    """**버킷에 다른 규칙으로 올라간 객체가 섞여 있어도 백필이 죽지 않는다.**

    `_verify/` 객체가 실제로 있다 (`datastore/minio-init/init.sh`).
    """
    assert parse_key(key) is None


# --- 범위 ----------------------------------------------------------------


def test_범위는_to_를_포함한다():
    """[02 §6] 의 `--to` 설명이 "포함" 이다."""
    request = build_request("fashion", "2026-09-01", "2026-09-03")

    assert list(request.days()) == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]


def test_하루짜리_범위():
    request = build_request("fashion", "2026-09-03", "2026-09-03")

    assert list(request.days()) == [date(2026, 9, 3)]


def test_도메인_슬러그를_소문자로_받는다():
    assert build_request("FASHION", "2026-09-01", "2026-09-01").domain == "fashion"


def test_허용_목록_밖_도메인은_거절한다():
    """모드 B 는 `classify` 를 타지 않으므로 `DOMAIN_VALUES` 방어를 여기서 한 번 더 세운다.

    통과시키면 `dev` 와 `DEVELOP` 이 별개 분야로 나뉘는 종류의 오염이 들어온다 ([01 §6]).
    """
    with pytest.raises(ConfigError, match="허용 목록에 없는 domain"):
        build_request("development", "2026-09-01", "2026-09-01")


@pytest.mark.parametrize("domain", [None, "", "   "])
def test_도메인이_없으면_거절한다(domain):
    with pytest.raises(ConfigError, match="--domain"):
        build_request(domain, "2026-09-01", "2026-09-01")


def test_from_이_to_보다_늦으면_거절한다():
    with pytest.raises(ConfigError, match="--from 이 --to 보다 늦다"):
        build_request("fashion", "2026-09-03", "2026-09-01")


@pytest.mark.parametrize("raw", [None, "", "2026/09/03", "어제", "2026-13-01"])
def test_날짜_형태가_아니면_거절한다(raw):
    """**여기서 죽는 것이 맞다.** 범위가 틀린 백필은 아무것도 안 하거나 엉뚱한 구간을 다시
    처리하고, 둘 다 조용하다."""
    with pytest.raises(ConfigError):
        parse_day(raw, flag="--from")


def test_공백은_다듬는다():
    assert parse_day(" 2026-09-03 ", flag="--from") == date(2026, 9, 3)


# --- 국가 ------------------------------------------------------------------


def envelope(source: str, countries: dict[str, str] | None = None) -> dict:
    parsed = ("fashion", source, "rss", "854414")
    return _envelope(
        "raw-data",
        KEY,
        parsed,
        checksum=None,
        collected_at=None,
        countries=countries or {},
    )


def test_소스_이름으로_국가를_채운다():
    """국가는 소스의 속성이라 `article.json` 에 없다. 지도를 찾는 것이 유일한 길이다."""
    assert envelope("vogue", {"vogue": "KR"})["source_country"] == "KR"


def test_지도에_없는_소스는_XX_다():
    """비워 두면 이 경로로 재처리한 문서만 국가를 잃는다."""
    assert envelope("vogue", {"hn": "XX"})["source_country"] == UNKNOWN_COUNTRY
    assert envelope("vogue")["source_country"] == UNKNOWN_COUNTRY


def test_지도의_값도_모양을_검사한다():
    """거울이 오염돼도 적재 끝의 CHECK 위반으로 번지지 않게 한다."""
    assert envelope("vogue", {"vogue": "kr"})["source_country"] == "KR"
    assert envelope("vogue", {"vogue": "KOR"})["source_country"] == UNKNOWN_COUNTRY
