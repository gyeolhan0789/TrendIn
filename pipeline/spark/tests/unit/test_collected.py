"""장부 뷰에서 봉투를 만드는 경로 ([09 §4] 층 1, S15P21A102-247).

DB 없이 검사한다. 여기서 보는 것은 **계약**이다 — 뷰의 칸 이름이 봉투의 필드 이름과
같은지, 없는 칸이 상수로 채워지는지, 뷰가 없을 때 조용히 0건으로 끝나지 않는지.
"""

from __future__ import annotations

import pathlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from trendin.spark.common.config import Config, ConfigError, load_config
from trendin.spark.ingest import collected
from trendin.spark.io.schema import CORRUPT_FIELD, EVENT_SCHEMA

# 진짜 `conf/` 를 읽는다. 창의 기본값이 거기 하나뿐이라 대역으로는 확인할 수 없다.
CONF_DIR = pathlib.Path(__file__).resolve().parents[2] / "conf"


def config(**overrides) -> Config:
    data = {"minio": {"buckets": {"raw": "raw-data"}}}
    return Config(data | overrides, profile="test")


def fake_connection(rows, *, view_exists=True):
    """`jdbc.connection` 대역. 존재 확인과 목록 조회가 같은 커서를 쓴다."""

    class Cursor:
        def __init__(self):
            self.last = None

        def execute(self, sql, params=None):
            self.last = sql

        def fetchone(self):
            return (view_exists,)

        def fetchall(self):
            return rows

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Conn:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection(_config):
        yield Conn()

    return connection


# --- 창 -------------------------------------------------------------------


def test_기본_창은_Kafka_보존이던_7일이다():
    """걷어내면서 관용을 줄이면 그만큼이 조용히 백필 대상이 된다.

    값을 `conf/base.yaml` 에서 읽는다. 코드에 기본값을 또 두면 두 곳이 같은 것을 말하게
    되고, 한쪽만 고쳐졌을 때 어느 쪽이 이겼는지 알 수 없다 (S15P21A102-247 코드리뷰).
    """
    assert collected.lookback(load_config("local", conf_dir=CONF_DIR, env={})) == timedelta(
        hours=168
    )


def test_설정에_창이_없으면_죽는다():
    """기본값이 코드에 없으므로 `base.yaml` 에서 키가 사라지면 여기서 드러난다."""
    with pytest.raises(ConfigError):
        collected.lookback(config())


def test_설정이_창을_덮는다():
    cfg = config(ingest={"ledger": {"lookback_hours": 6}})

    assert collected.lookback(cfg) == timedelta(hours=6)


@pytest.mark.parametrize("hours", [0, -1])
def test_창이_양수가_아니면_죽는다(hours: int):
    """0 이면 아무것도 안 읽고 조용히 끝난다 — 수집 0건과 구분되지 않는다."""
    with pytest.raises(ConfigError):
        collected.lookback(config(ingest={"ledger": {"lookback_hours": hours}}))


# --- 뷰와 봉투의 계약 -------------------------------------------------------


def test_뷰의_칸_이름이_봉투의_필드_이름이다():
    """별칭을 붙이는 자리가 뷰 하나뿐이어야 어긋났을 때 볼 데가 하나다."""
    envelope_fields = {field.name for field in EVENT_SCHEMA.fields}

    assert set(collected.VIEW_COLUMNS) <= envelope_fields


def test_봉투가_스키마의_칸을_하나도_빠뜨리지_않는다():
    """빠진 칸은 프레임 조립에서 `None` 이 되고, 그건 계약 위반과 구분되지 않는다."""
    row = {name: None for name in collected.VIEW_COLUMNS}

    envelope = collected._envelope(row, bucket="raw-data")

    assert set(envelope) == {field.name for field in EVENT_SCHEMA.fields}


def test_발급_실행이_없어져서_run_id_는_비운다():
    """값의 뜻이 "이 기사를 발급한 수집 실행" 이었는데 그런 실행이 없다. 지어내지 않는다."""
    envelope = collected._envelope(
        {name: None for name in collected.VIEW_COLUMNS}, bucket="raw-data"
    )

    assert envelope["run_id"] is None
    assert envelope["status"] == "success"
    assert envelope["record_count"] == 1
    assert envelope["format"] == "json"
    assert envelope[CORRUPT_FIELD] is None


# --- 읽기 -----------------------------------------------------------------


def test_창_안의_행이_봉투가_된다(monkeypatch):
    row = (
        "vogue-123", "fashion", "vogue", "123",
        "fashion/vogue/rss/2026/09/03/123/article.json", None,
        "https://example.test/a", "제목",
        "2026-09-03T10:00:00.000000+09:00", "2026-09-03T11:00:00.000000+09:00",
        "sha256-abc", False, False, "KR",
    )
    monkeypatch.setattr(collected.jdbc, "connection", fake_connection([row]))

    envelopes = collected.list_events(config(), since=datetime.now(timezone.utc))

    assert len(envelopes) == 1
    assert envelopes[0]["event_id"] == "vogue-123"
    assert envelopes[0]["bucket"] == "raw-data"
    assert envelopes[0]["members_only"] is False
    assert envelopes[0]["paywalled"] is False
    assert envelopes[0]["source_country"] == "KR"


def test_뷰가_없으면_조용히_0건이_아니라_죽는다(monkeypatch):
    """빈 목록을 주면 "수집이 0건이었다" 와 구분되지 않고, 그 차이는 며칠 뒤에야 드러난다."""
    monkeypatch.setattr(collected.jdbc, "connection", fake_connection([], view_exists=False))

    with pytest.raises(ConfigError, match=collected.VIEW):
        collected.list_events(config(), since=datetime.now(timezone.utc))
