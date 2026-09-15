"""[07] 임계값의 설정 거부 — `extract`·`registry` 와 같은 규약이다.

**비어 있으면 Job 이 시작하지 않는다.** 근거 없는 문턱으로 서비스 테이블에 배지를 다는 것보다
거부가 싸다. `base.yaml` 만으로는 못 돌고 `local.yaml` 이 잠정값을 채우는 것도 여기서 지킨다 —
그 관계가 깨지면 운영에서 측정 없이 도는 길이 열린다.
"""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError, load_config
from trendin.spark.metrics.thresholds import (
    MIN_SOURCES,
    REQUIRED,
    AggregateThresholds,
)

BASE = {
    "periods": ["24H"],
    "reference_day_offset": 1,
    "recompute_window_days": 30,
    "history_bucket": "1D",
    "thresholds": {
        "active_window_days": 30,
        "current": {"top_n": 5},
        "rising": {
            "min_growth_amount": 3,
            "min_growth_rate": 50,
            "min_mention_count": 5,
            "top_n": 5,
        },
        "new": {"windows": {"24H": {"quiet_days": 7, "quiet_max": 1, "min_mentions": 5}}},
        "zscore": {"background_days": 90, "min_background_days": 10, "min_z": 2.0},
        "author_daily_cap": None,
    },
}


def config(**overrides) -> Config:
    import copy

    data = {"aggregate": copy.deepcopy(BASE)}
    for path, value in overrides.items():
        node = data["aggregate"]
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part]
        if value is _MISSING:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value
    return Config(data, profile="test")


_MISSING = object()


# --- 읽기 -----------------------------------------------------------------


def test_설정을_그대로_읽는다():
    thresholds = AggregateThresholds.from_config(config())
    assert thresholds.recompute_window_days == 30
    assert thresholds.rising.min_mention_count == 5
    assert thresholds.new_windows["24H"].quiet_days == 7
    assert thresholds.zscore.min_z == 2.0


def test_저자_상한은_기본이_꺼짐이다():
    """[07 §8] — 실측에서 0.1% 행에만 걸려 넣지 않았다. 켜려면 원자료 재집계가 선행이다."""
    assert AggregateThresholds.from_config(config()).author_daily_cap is None


def test_소스_하한은_설정이_아니라_코드다():
    """[07 §6] 이 못 박은 값이라 `conf` 에서 낮출 수 있게 두지 않는다."""
    assert MIN_SOURCES == 2


# --- 거부 -----------------------------------------------------------------


@pytest.mark.parametrize("key", REQUIRED)
def test_필수값이_비면_거부한다(key):
    with pytest.raises(ConfigError) as error:
        AggregateThresholds.from_config(config(**{key: None}))
    assert key in str(error.value)


def test_빠진_키를_전부_알려준다():
    """하나씩 채우며 재실행하게 만들지 않는다."""
    with pytest.raises(ConfigError) as error:
        AggregateThresholds.from_config(
            config(**{"recompute_window_days": None, "thresholds.zscore.min_z": None})
        )
    message = str(error.value)
    assert "recompute_window_days" in message and "min_z" in message


def test_계산하는_기간의_NEW_창이_없으면_거부한다():
    with pytest.raises(ConfigError) as error:
        AggregateThresholds.from_config(config(periods=["24H", "7D"]))
    assert "windows.7D" in str(error.value)


def test_안_쓰는_기간의_창은_요구하지_않는다():
    """`periods` 에서 뺀 기간의 값까지 채우게 하면 쓰지도 않는 숫자를 짓게 된다."""
    thresholds = AggregateThresholds.from_config(config(periods=["24H"]))
    assert set(thresholds.new_windows) == {"24H"}


def test_모르는_기간은_거부한다():
    with pytest.raises(ConfigError) as error:
        AggregateThresholds.from_config(config(periods=["1H"]))
    assert "1H" in str(error.value)


def test_기간이_비면_거부한다():
    with pytest.raises(ConfigError):
        AggregateThresholds.from_config(config(periods=[]))


def test_지원하지_않는_버킷_폭은_거부한다():
    """조용히 하루로 떨어뜨리면 설정에 적어 둔 것과 다른 폭을 받게 된다."""
    with pytest.raises(ConfigError) as error:
        AggregateThresholds.from_config(config(history_bucket="15M"))
    assert "15M" in str(error.value)


def test_버킷_폭_기본은_일이다():
    assert AggregateThresholds.from_config(config()).hourly_history is False


def test_시간_버킷을_설정으로_켤_수_있다():
    """백엔드의 `24H` 화면이 1시간 폭을 기대한다 ([07 §3])."""
    thresholds = AggregateThresholds.from_config(config(history_bucket="1H"))

    assert thresholds.history_bucket == "1H"
    assert thresholds.hourly_history is True


# --- 지평 -----------------------------------------------------------------


def test_지평이_30D_NEW_의_120일을_덮는다():
    """[07 §6] 의 표 — `30D` 는 최근 30일 + 그 이전 90일을 본다."""
    thresholds = AggregateThresholds.from_config(
        config(
            periods=["24H", "7D", "30D"],
            **{
                "thresholds.new.windows": {
                    "24H": {"quiet_days": 7, "quiet_max": 1, "min_mentions": 5},
                    "7D": {"quiet_days": 30, "quiet_max": 2, "min_mentions": 10},
                    "30D": {"quiet_days": 90, "quiet_max": 3, "min_mentions": 20},
                }
            },
        )
    )
    assert thresholds.horizon_days() == 121


# --- 저장소의 실제 설정 ------------------------------------------------------


def test_base_는_여전히_비어_있다():
    """**확정은 `base.yaml` 로 옮기는 일이다** ([07 §6]). 프로파일이 잠정값을 채워 Job 이
    도는 것과, 그 값이 확정된 것은 다르다. 여기가 채워지면 그 구분이 사라진다.
    """
    import pathlib

    import yaml

    conf = pathlib.Path(__file__).resolve().parents[2] / "conf"
    with open(conf / "base.yaml", encoding="utf-8") as handle:
        base = yaml.safe_load(handle)
    thresholds = base["aggregate"]["thresholds"]
    assert thresholds["rising"]["min_growth_amount"] is None
    assert thresholds["zscore"]["min_z"] is None


def test_dev_도_local_과_같은_잠정값으로_돈다():
    """2026-09-15 에 EC2 에서 지표를 내려고 `local.yaml` 값을 `dev.yaml` 로 옮겼다.

    두 프로파일이 갈리면 로컬에서 뽑아 본 목록과 화면에 나가는 것이 달라진다.
    """
    assert AggregateThresholds.from_config(load_config("dev")) == AggregateThresholds.from_config(
        load_config("local")
    )


def test_local_은_잠정값으로_돈다():
    thresholds = AggregateThresholds.from_config(load_config("local"))
    assert thresholds.periods == ("24H", "7D", "30D")
    assert thresholds.recompute_window_days == 30


def test_base_가_실측값을_들고_있다():
    """`recompute_window_days` 는 알고리즘 문턱이 아니라 실측이라 base 에 박혀 있다 ([07 §2])."""
    assert load_config("dev").get("aggregate.recompute_window_days") == 30
