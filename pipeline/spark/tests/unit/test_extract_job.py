"""extract Job 진입점의 승격 갈래 (`spark/jobs/extract.py`).

여기서 지키는 것은 **언제 승격하지 않는가**다. 승격은 되돌릴 수 없으므로([05 §1])
`keywords` 싱크가 `None` 이 되는 자리가 곧 안전장치이고, 그 갈래가 둘이다.

| 갈래 | 막는 것 |
| --- | --- |
| 선행 조건 부재 (`--allow-missing-keyword-unique`) | 할 수 없는데 돌았다 |
| `--skip-promotion` | **보려고만 했는데 올라가 버렸다** |

뒤의 것이 없어서 2026-09-17 실체 인식 교체 실측이 `keywords` 1,166건과 함께 나왔다.
문턱은 후보 분포를 본 뒤라야 정할 수 있는데([10 §4] S6) 분포를 뜨는 실행과 실제로 올리는
실행이 갈려 있지 않았다.
"""

from __future__ import annotations

import extract
import pytest

from trendin.spark.common.cli import build_parser
from trendin.spark.common.config import Config, ConfigError


def config(*, required=True) -> Config:
    return Config({"extract": {"registry": {"required": required}}}, profile="local")


class FakeSink:
    """`io/keywords.KeywordSink` 의 선행 조건 질의 둘만."""

    def __init__(self, *, tables=True, unique=True):
        self._tables = tables
        self._unique = unique

    def service_tables_ready(self) -> bool:
        return self._tables

    def unique_constraint_ready(self) -> bool:
        return self._unique


def test_skip_promotion_이면_싱크를_만들지도_않는다(monkeypatch):
    """선행 조건을 **보지 않는다.** 어차피 건드리지 않을 표라, 여기서 죽으면 분포를
    뜨려던 실행이 백엔드 상태에 묶인다."""

    def 만들면_안_된다(config):
        raise AssertionError("KeywordSink 를 만들면 DB 를 본다 — 볼 이유가 없는 회차다")

    monkeypatch.setattr(extract, "KeywordSink", 만들면_안_된다)

    sink = extract._keyword_sink(
        config(required=True), allow_missing_unique=False, skip_promotion=True
    )

    assert sink is None


def test_스위치가_없으면_선행_조건이_갖춰진_채_승격한다(monkeypatch):
    ready = FakeSink()
    monkeypatch.setattr(extract, "KeywordSink", lambda config: ready)

    sink = extract._keyword_sink(
        config(required=True), allow_missing_unique=False, skip_promotion=False
    )

    assert sink is ready


@pytest.mark.parametrize(
    ("missing", "부재"),
    [({"tables": False}, "테이블"), ({"unique": False}, "UNIQUE")],
)
def test_선행_조건이_없으면_기본은_죽는다(monkeypatch, missing, 부재):
    """fail-closed 다 ([09 §7] 항목 2). 조용히 건너뛰면 증상이 화면에서야 나타난다."""
    monkeypatch.setattr(extract, "KeywordSink", lambda config: FakeSink(**missing))

    with pytest.raises(ConfigError, match=부재):
        extract._keyword_sink(
            config(required=True), allow_missing_unique=False, skip_promotion=False
        )


def test_인자_둘은_서로_다른_뜻이라_따로_있다():
    """`--allow-missing-keyword-unique` 로 `--skip-promotion` 을 갈음하지 않는다 — 저것은
    선행 조건이 **있으면** 승격하므로, 분포만 보려는 실행에서는 아무것도 막지 못한다."""
    args = build_parser("extract", extract.add_arguments).parse_args(["--skip-promotion"])

    assert args.skip_promotion
    assert not args.allow_missing_unique
