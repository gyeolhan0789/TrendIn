"""`concept.*` 설정 — 정책값이지만 지운 것은 받지 않는다."""

from __future__ import annotations

import pytest

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.concept.thresholds import ConceptThresholds

FULL = {
    "window_days": 30,
    "seed_dir": "spark/conf/concepts",
    "unmapped": {"min_articles": 5, "context_samples": 20},
}


def config(concept: dict) -> Config:
    return Config({"concept": concept}, profile="test")


def test_전부_있으면_읽는다():
    t = ConceptThresholds.from_config(config(FULL))
    assert (t.window_days, t.min_articles, t.context_samples) == (30, 5, 20)
    assert t.seed_dir == "spark/conf/concepts"


def test_비어_있는_키를_이름_붙여_거부한다():
    partial = {
        **FULL,
        "window_days": None,
        "unmapped": {"min_articles": 5, "context_samples": None},
    }
    with pytest.raises(ConfigError) as error:
        ConceptThresholds.from_config(config(partial))
    message = str(error.value)
    assert "concept.window_days" in message
    assert "concept.unmapped.context_samples" in message
    assert "concept.unmapped.min_articles" not in message


def test_구역이_통째로_없어도_이름_붙여_거부한다():
    with pytest.raises(ConfigError) as error:
        ConceptThresholds.from_config(Config({}, profile="test"))
    assert "concept.window_days" in str(error.value)


@pytest.mark.parametrize(
    "patch",
    [
        {"window_days": 0},
        {"unmapped": {"min_articles": 0, "context_samples": 20}},
        {"unmapped": {"min_articles": 5, "context_samples": 0}},
    ],
)
def test_1_미만은_거부한다(patch):
    with pytest.raises(ConfigError):
        ConceptThresholds.from_config(config({**FULL, **patch}))


def test_선택_키는_기본값이_있다():
    t = ConceptThresholds.from_config(
        config({k: v for k, v in FULL.items() if k in ("window_days", "unmapped")})
    )
    assert t.seed_dir == "spark/conf/concepts"
