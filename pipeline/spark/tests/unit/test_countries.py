"""국가 코드 한 벌 (`common/countries.py`).

이 파일이 지키는 것은 **세 층의 "판정 불가" 리터럴이 같다**는 것이다 (수집 계약 · 장부 뷰 ·
Spark). 어긋나면 같은 기사가 층에 따라 다른 나라를 갖게 되고, 증상이 "이동 경로에 없는
나라가 하나 더 있다" 로 나타난다.

**Spark 표현식(`country_column`)은 여기서 보지 않는다.** 세션이 필요해 층 1 테스트의 규약을
깨기 때문이고, 같은 규칙을 배치 경로로 덮는 테스트가
`tests/spark/test_extract_batch.test_국가를_모르거나_모양이_틀리면_XX_로_접힌다` 에 있다.
"""

from __future__ import annotations

import pytest

from trendin.common.collect.contracts import UNKNOWN_COUNTRY as COLLECT_UNKNOWN
from trendin.common.collect.ledger import DDL as LEDGER_DDL
from trendin.spark.common.countries import UNKNOWN_COUNTRY, normalize_country

# `normalize_country` 와 `country_column` 이 같이 받아야 하는 입력.
CASES = [
    ("KR", "KR"),
    ("IT", "IT"),
    # 소문자는 올려 받는다. 프로필 로더가 막지만 백필 경로는 그쪽을 지나지 않는다.
    ("kr", "KR"),
    ("  JP  ", "JP"),
    # 모양이 틀리면 흘리지 않는다 — 흘리면 적재 끝에서 CHECK 위반으로 터진다.
    ("KOR", UNKNOWN_COUNTRY),
    ("K", UNKNOWN_COUNTRY),
    ("", UNKNOWN_COUNTRY),
    ("K1", UNKNOWN_COUNTRY),
    (None, UNKNOWN_COUNTRY),
]


def test_판정_불가_리터럴이_세_층에서_같다():
    """한 벌로 모으지 못하는 이유는 층마다 다르다 (`common/countries.py` 의 머리말)."""
    assert UNKNOWN_COUNTRY == COLLECT_UNKNOWN
    assert f"coalesce(country, '{UNKNOWN_COUNTRY}')" in LEDGER_DDL


@pytest.mark.parametrize(("value", "expected"), CASES)
def test_국가_코드를_기본키에_넣을_수_있는_모양으로_접는다(value, expected):
    assert normalize_country(value) == expected


def test_서비스_표의_제약과_같은_모양만_통과한다():
    """`ck_keyword_country_daily_metrics_country_code` 가 `^[A-Z]{2}$` 다.

    어떤 입력이 와도 그 제약을 통과하는 값만 나와야 한다 — 이 함수가 적재 직전의 마지막
    관문이고, 통과시키면 증상이 원인에서 네 층 떨어진 자리에 나타난다.
    """
    import re

    for value, _ in CASES:
        assert re.fullmatch(r"^[A-Z]{2}$", normalize_country(value)), f"{value!r} 가 새어 나갔다"
