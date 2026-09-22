"""덤프 두 장 맞대기 — 합계가 같아도 회귀가 드러나야 한다.

`unmapped → resolved` 와 `resolved → deferred` 가 같은 수로 일어나면 매핑률은 그대로다.
그것을 "변화 없음" 으로 읽으면 사전을 늘려 품질을 깎고도 모른다. 여기서 고정하는 것이 그거다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "concept-dump-diff.py"


def _load_script():
    """하이픈이 든 스크립트라 import 문으로 못 읽는다 (`test_extract_snapshots` 와 같은 사정)."""
    spec = importlib.util.spec_from_file_location("concept_dump_diff", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["concept_dump_diff"] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def dump(path: Path, outcomes: dict[tuple[int, str], str], **meta) -> Path:
    base = {
        "t": "meta", "domain": "fashion", "window_days": 30, "dictionary_version": 1,
        "seed_in_memory": True, "concepts": 10, "expressions": 20, "articles": 2,
        "rows": 0, "context": 0, "deferred": 0, "unmapped": 0,
    }
    lines = [json.dumps({**base, **meta}, ensure_ascii=False)]
    for (article_id, normalized), outcome in sorted(outcomes.items()):
        lines.append(json.dumps(
            {"t": outcome, "article_id": article_id, "lang": "ko", "normalized": normalized},
            ensure_ascii=False,
        ))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run(tmp_path, before_outcomes, after_outcomes, *argv):
    before = dump(tmp_path / "before.jsonl", before_outcomes)
    after = dump(tmp_path / "after.jsonl", after_outcomes)
    return script.main([str(before), str(after), *argv])


def test_매핑률이_같아도_회귀가_드러난다(tmp_path, capsys):
    run(
        tmp_path,
        {(1, "조끼"): "resolved", (1, "제니"): "unmapped"},
        {(1, "조끼"): "deferred", (1, "제니"): "resolved"},
    )

    out = capsys.readouterr().out
    assert "resolved  → deferred" in out
    assert "회귀 1 · 좋아짐 1" in out


def test_회귀가_없으면_관문을_통과한다(tmp_path):
    assert run(
        tmp_path,
        {(1, "조끼"): "unmapped"},
        {(1, "조끼"): "resolved"},
        "--fail-on-regression",
    ) == 0


def test_회귀가_있으면_관문이_막는다(tmp_path):
    assert run(
        tmp_path,
        {(1, "조끼"): "resolved"},
        {(1, "조끼"): "unmapped"},
        "--fail-on-regression",
    ) == 1


def test_한쪽에만_있는_표기는_회귀도_개선도_아니다(tmp_path, capsys):
    # 창이 하루만 밀려도 수백 건이 이렇게 된다. 회귀로 세면 관문이 늘 빨개진다.
    run(tmp_path, {(1, "조끼"): "resolved"}, {(2, "부츠"): "resolved"})

    out = capsys.readouterr().out
    assert "말뭉치가 달라졌다" in out
    assert "회귀 0 · 좋아짐 0 · 모호해짐 0 · 말뭉치 차이 2" in out


def test_문맥으로_갈린_것은_붙은_쪽으로_세고_약해진_것만_따로_센다(tmp_path, capsys):
    # `resolved → context` 는 기사에 개념이 남으므로 회귀가 아니다. 그래도 사전이 지저분해진
    # 신호라 따로 센다. `context → deferred` 는 붙던 것이 안 붙게 된 것이라 회귀다.
    run(
        tmp_path,
        {(1, "조끼"): "resolved", (1, "코트"): "context"},
        {(1, "조끼"): "context", (1, "코트"): "deferred"},
    )

    out = capsys.readouterr().out
    assert "모호해졌다 (붙긴 붙는다)" in out
    assert "회귀 1 · 좋아짐 0 · 모호해짐 1" in out


def test_json_출력은_이동을_그대로_싣는다(tmp_path, capsys):
    run(tmp_path, {(1, "조끼"): "resolved"}, {(1, "조끼"): "deferred"}, "--json")

    payload = json.loads(capsys.readouterr().out)
    assert payload["moves"] == {"resolved->deferred": 1}
    assert payload["regressions"] == 1
    assert payload["concepts_comparable"] is False


def test_창이_다르면_경고한다(tmp_path, capsys):
    before = dump(tmp_path / "before.jsonl", {}, window_days=30)
    after = dump(tmp_path / "after.jsonl", {}, window_days=7)

    script.main([str(before), str(after)])

    assert "window_days 가 다르다" in capsys.readouterr().err


def test_깨진_덤프는_조용히_넘어가지_않는다(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps({"t": "resolved", "article_id": 1, "lang": "ko",
                                "normalized": "조끼"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="meta"):
        script.read(path)
