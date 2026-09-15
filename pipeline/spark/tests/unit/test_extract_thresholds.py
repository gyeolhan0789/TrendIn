"""`extract` 설정 ([04 §10] · `conf/base.yaml`). 층 1."""

from __future__ import annotations

import pathlib

import pytest

from trendin.spark.common.config import Config, ConfigError, load_config
from trendin.spark.extract.thresholds import DomainOptions, ExtractThresholds, lexicon_dir

CONF_DIR = pathlib.Path(__file__).resolve().parents[2] / "conf"

FULL = {
    "corpus_window_days": 30,
    "df_min_ratio": 0.01,
    "df_max_ratio": 0.3,
    "score_weights": {"c_value": 0.3, "bm25": 0.4, "title": 0.3},
    "per_document_top_k": 10,
    "score_floor": 0.2,
}


def config(extract: dict) -> Config:
    return Config({"extract": extract}, profile="test")


def test_비어_있는_키를_전부_이름_붙여_거부한다():
    partial = {**FULL, "df_min_ratio": None, "score_weights": {"c_value": 0.3, "bm25": None}}

    with pytest.raises(ConfigError) as error:
        ExtractThresholds.from_config(config(partial))

    message = str(error.value)
    assert "extract.df_min_ratio" in message
    assert "extract.score_weights.bm25" in message
    assert "extract.score_weights.title" in message
    assert "extract.corpus_window_days" not in message


def test_기본값이_있는_키는_없어도_된다():
    thresholds = ExtractThresholds.from_config(config(FULL))

    assert thresholds.ngram_max == 3
    assert (thresholds.min_chars, thresholds.max_chars) == (2, 40)
    assert (thresholds.bm25_k1, thresholds.bm25_b) == (1.2, 0.75)


@pytest.mark.parametrize(
    "broken",
    [
        {"df_min_ratio": 0.5, "df_max_ratio": 0.1},  # 하한 > 상한
        {"df_max_ratio": 1.5},
        {"per_document_top_k": 0},
        {"score_weights": {"c_value": 0, "bm25": 0, "title": 0}},
        {"ngram_max": 0},
    ],
)
def test_말이_안_되는_값은_거부한다(broken):
    with pytest.raises(ConfigError):
        ExtractThresholds.from_config(config({**FULL, **broken}))


def test_도메인_옵션은_없는_도메인이면_기본값():
    options = DomainOptions.from_config(
        config({"domains": {"fashion": {"code_identifiers": False}}}), domain="dev"
    )
    assert options == DomainOptions()

    fashion = DomainOptions.from_config(
        config({"domains": {"fashion": {"code_identifiers": False, "hashtag_weight": 1.5}}}),
        domain="fashion",
    )
    assert fashion.code_identifiers is False and fashion.hashtag_weight == 1.5


def test_사전_디렉터리_기본값():
    assert lexicon_dir(config({})) == "spark/conf/lexicon"


# --- 저장소의 실제 conf ----------------------------------------------------------------


def test_base_는_여전히_비어_있다():
    """**확정은 `base.yaml` 로 옮기는 일이다** ([09 §7] 항목 5). 프로파일이 잠정값을 채워
    Job 이 도는 것과, 그 값이 확정된 것은 다르다. 여기가 채워지면 그 구분이 사라진다.
    """
    import yaml

    with open(CONF_DIR / "base.yaml", encoding="utf-8") as handle:
        base = yaml.safe_load(handle)
    assert base["extract"]["df_min_ratio"] is None
    assert base["extract"]["score_weights"]["c_value"] is None


def test_dev_도_local_과_같은_잠정값으로_돈다():
    """2026-09-15 에 EC2 에서 처리 단계를 돌리려고 `local.yaml` 값을 `dev.yaml` 로 옮겼다.

    두 프로파일이 갈리면 로컬에서 본 목록과 서버에 쌓이는 것이 달라진다.
    """
    dev = ExtractThresholds.from_config(load_config("dev", conf_dir=CONF_DIR, env={}))
    local = ExtractThresholds.from_config(load_config("local", conf_dir=CONF_DIR, env={}))
    assert dev == local


def test_local_은_잠정값으로_돈다():
    thresholds = ExtractThresholds.from_config(load_config("local", conf_dir=CONF_DIR, env={}))
    assert thresholds.per_document_top_k == 30
    assert (
        DomainOptions.from_config(
            load_config("local", conf_dir=CONF_DIR, env={}), domain="fashion"
        ).code_identifiers
        is False
    )


def test_고유명사_축은_없어도_돈다():
    """`REQUIRED` 가 아니다 — 0 이면 옛 동작 그대로라 비어 있는 것이 위험하지 않다."""
    config = load_config("local", conf_dir=CONF_DIR, env={})
    data = config.as_dict()
    data["extract"]["score_weights"].pop("latin", None)
    data["extract"]["score_weights"]["proper"] = None
    thresholds = ExtractThresholds.from_config(Config(data, profile="test"))
    assert (thresholds.weight_latin, thresholds.weight_proper) == (0.0, 0.0)


def test_local_이_고유명사_축을_켠다():
    thresholds = ExtractThresholds.from_config(load_config("local", conf_dir=CONF_DIR, env={}))
    assert thresholds.weight_latin > 0
    # 형태소 태그는 신뢰도가 낮아 라틴보다 작아야 한다 (`tokenize.Token.is_proper`).
    assert 0 < thresholds.weight_proper < thresholds.weight_latin
