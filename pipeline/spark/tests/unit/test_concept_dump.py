"""사전 변경 전후를 맞대기 위한 덤프 — 표기 하나가 정확히 한 줄이어야 셈이 맞는다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import concept as job
import pytest

from trendin.spark.common.config import ConfigError
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.mapping import ConceptRow, Deferred, Unmapped

DICTIONARY = Dictionary(
    [Concept(1, "vest", "apparel")], [Expression(10, 1, "en", "vest")]
)


def write(tmp_path, **overrides):
    path = tmp_path / "out" / "run.jsonl"
    arguments = {
        "domain": "fashion",
        "window_days": 30,
        "dictionary_version": 7,
        "seed_in_memory": True,
        "seed_dir": Path("spark/conf/concepts"),
        "dictionary": DICTIONARY,
        "rows": [ConceptRow(2, 1, (10,), "DICT")],
        "unmapped": [Unmapped(2, "ko", "제니", "제니", None)],
        "deferred": [Deferred(1, "ko", "어그", (3, 9))],
        "resolved": {1: (("en", "vest"),), 2: ()},
        "context": {1: (), 2: (("ko", "코트"),)},
    }
    job._dump(path, **{**arguments, **overrides})
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_첫_줄은_meta_이고_나머지_수를_요약한다(tmp_path):
    lines = write(tmp_path)

    assert lines[0]["t"] == "meta"
    assert lines[0]["dictionary_version"] == 7
    assert lines[0]["seed_in_memory"] is True
    assert (lines[0]["articles"], lines[0]["rows"], lines[0]["context"]) == (2, 1, 1)


def test_표기_하나는_한_줄로만_나온다(tmp_path):
    lines = write(tmp_path)

    surfaces = [
        (line["article_id"], line["lang"], line["normalized"])
        for line in lines
        if line["t"] in ("resolved", "context", "deferred", "unmapped")
    ]
    assert sorted(surfaces) == [
        (1, "en", "vest"), (1, "ko", "어그"), (2, "ko", "제니"), (2, "ko", "코트"),
    ]
    assert len(surfaces) == len(set(surfaces))


def test_줄이_정렬돼_있어_두_실행을_그대로_맞댈_수_있다(tmp_path):
    shuffled = write(
        tmp_path,
        deferred=[Deferred(1, "ko", "어그", (9, 3))],
        resolved={2: (), 1: (("en", "vest"),)},
        context={2: (("ko", "코트"),), 1: ()},
    )
    plain = write(tmp_path)

    assert shuffled == plain


def test_디렉터리가_없으면_만든다(tmp_path):
    assert write(tmp_path)
    assert (tmp_path / "out" / "run.jsonl").exists()


def test_meta_는_어느_사전을_읽었는지_남긴다(tmp_path):
    # 두 덤프가 무엇과 무엇을 맞댄 것인지 파일만 보고 알 수 있어야 한다.
    lines = write(tmp_path)

    assert lines[0]["seed_dir"].endswith("concepts")


def test_메모리_사전은_dry_run_없이_쓸_수_없다():
    args = argparse.Namespace(seed_in_memory=True, dry_run=False, seed_dir=None)

    with pytest.raises(ConfigError, match="--seed-in-memory"):
        job.run(None, None, args)


def test_검수를_안_거친_사전_폴더는_적재에_쓸_수_없다():
    # git 이 승인 계층이다 — 명령줄로 아무 폴더나 운영에 붓게 두면 그 규약이 무너진다.
    args = argparse.Namespace(seed_in_memory=False, dry_run=False, seed_dir=Path("/tmp/wd"))

    with pytest.raises(ConfigError, match="--seed-dir"):
        job.run(None, None, args)
