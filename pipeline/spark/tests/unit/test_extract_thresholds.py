"""`extract` 설정 ([04 §10] · `conf/base.yaml`). 층 1."""

from __future__ import annotations

import pathlib

import pytest

from trendin.spark.common.config import Config, ConfigError, load_config
from trendin.spark.extract.thresholds import (
    DomainOptions,
    ExtractThresholds,
    adapter_spec,
    lexicon_dir,
    recognizer_spec,
)

CONF_DIR = pathlib.Path(__file__).resolve().parents[2] / "conf"

FULL = {"per_document_top_k": 20, "score_floor": 0.2}


def config(extract: dict) -> Config:
    return Config({"extract": extract}, profile="test")


def profile(name: str) -> Config:
    return load_config(name, conf_dir=CONF_DIR, env={})


def test_비어_있는_키를_전부_이름_붙여_거부한다():
    with pytest.raises(ConfigError) as error:
        ExtractThresholds.from_config(config({"per_document_top_k": None, "score_floor": None}))

    message = str(error.value)
    assert "extract.per_document_top_k" in message and "extract.score_floor" in message


def test_기본값이_있는_키는_없어도_된다():
    thresholds = ExtractThresholds.from_config(config(FULL))
    assert (thresholds.min_chars, thresholds.max_chars) == (2, 40)
    assert (thresholds.bm25_k1, thresholds.bm25_b) == (1.2, 0.75)


@pytest.mark.parametrize(
    "broken",
    [
        {"per_document_top_k": 0},
        {"score_floor": 1.5},
        {"score_floor": -0.1},
        {"candidate": {"min_chars": 10, "max_chars": 2}},
    ],
)
def test_말이_안_되는_값은_거부한다(broken):
    with pytest.raises(ConfigError):
        ExtractThresholds.from_config(config({**FULL, **broken}))


def test_base_는_여전히_비어_있다():
    """**확정은 `base.yaml` 로 옮기는 일이다** ([09 §7] 항목 5). 프로파일이 잠정값을 채워
    Job 이 도는 것과, 그 값이 확정된 것은 다르다. 여기가 채워지면 그 구분이 사라진다.
    """
    import yaml

    with open(CONF_DIR / "base.yaml", encoding="utf-8") as handle:
        base = yaml.safe_load(handle)
    assert base["extract"]["per_document_top_k"] is None
    assert base["extract"]["score_floor"] is None


def test_dev_도_local_과_같은_잠정값으로_돈다():
    """두 프로파일이 갈리면 로컬에서 본 목록과 서버에 쌓이는 것이 달라진다."""
    assert ExtractThresholds.from_config(profile("dev")) == ExtractThresholds.from_config(
        profile("local")
    )


def test_local_은_잠정값으로_돈다():
    thresholds = ExtractThresholds.from_config(profile("local"))
    assert thresholds.per_document_top_k == 30
    assert thresholds.score_floor == 0.2


# --- 인식기 -------------------------------------------------------------------------


def test_인식기_설정이_도메인_라벨을_싣는다():
    spec = recognizer_spec(profile("local"), domain="fashion")

    assert spec.model == "urchade/gliner_multi-v2.1"
    assert spec.threshold == 0.15
    # 색상을 뺀 것이 F1 0.470 → 0.504 다 (`scratchpad/kwlab/RESULTS.md` §2.2).
    assert "브랜드" in spec.labels and "색상" not in spec.labels


def test_추론_장치의_기본은_cpu():
    """**배포에 GPU 가 없다.** 기본이 `auto` 면 GPU 가 있는 개발 PC 와 없는 서버가 같은
    설정으로 다르게 돌아, 재현되지 않는 성능 차이를 설정에서 찾을 수 없게 된다."""
    assert recognizer_spec(profile("local"), domain="fashion").device == "cpu"


def test_추론_장치를_환경변수로_덮는다():
    """돌리는 기계가 정하는 값이라 파일이 아니라 `EXTRACT_DEVICE` 로 받는다."""
    loaded = load_config("local", conf_dir=CONF_DIR, env={"EXTRACT_DEVICE": "cuda"})
    assert recognizer_spec(loaded, domain="fashion").device == "cuda"


@pytest.mark.parametrize("device", ["cpu", "cuda", "cuda:1", "auto"])
def test_받아들이는_장치_이름(device):
    spec = recognizer_spec(config({**FULL, "recognizer": {"device": device}}), domain="fashion")
    assert spec.device == device


def test_모르는_장치는_설정에서_거부한다():
    """torch 는 모르는 이름을 받아도 모델을 적재한 **뒤에** 죽는다 — 5초를 기다린 다음에야
    `cude` 를 `cuda` 로 고치게 된다."""
    with pytest.raises(ConfigError):
        recognizer_spec(config({**FULL, "recognizer": {"device": "cude"}}), domain="fashion")


def test_도메인마다_라벨이_다르다():
    fashion = recognizer_spec(profile("local"), domain="fashion").labels
    dev = recognizer_spec(profile("local"), domain="dev").labels

    assert fashion != dev
    assert "프로그래밍 언어" in dev


def test_모르는_도메인은_기본_라벨():
    """라벨이 없으면 모델이 아무것도 돌려주지 않아 증상이 "후보가 0개" 로만 나타난다."""
    assert DomainOptions.from_config(config(FULL), domain="없는도메인").labels


def test_라벨이_문자열_목록이_아니면_거부한다():
    with pytest.raises(ConfigError):
        DomainOptions.from_config(
            config({**FULL, "domains": {"fashion": {"labels": "브랜드"}}}), domain="fashion"
        )


# --- 언어별 후처리 -------------------------------------------------------------------


def test_일본어는_반만_켜져_있다():
    spec = adapter_spec(profile("local"), domain="fashion", directory=str(CONF_DIR / "lexicon"))

    assert spec.allows("ja", "브랜드") is True
    assert spec.allows("ja", "의류 품목") is False
    # 제한이 없는 언어는 전부 통과한다.
    assert spec.allows("ko", "의류 품목") is True


def test_사용자_사전이_실린다():
    """**한국어 성능의 절반이 여기서 온다** — 조사 경계와 고유명사 보호."""
    spec = adapter_spec(profile("local"), domain="fashion", directory=str(CONF_DIR / "lexicon"))
    assert spec.analyzer.user_words


def test_사전_디렉터리_기본값():
    assert lexicon_dir(config(FULL)) == "spark/conf/lexicon"
