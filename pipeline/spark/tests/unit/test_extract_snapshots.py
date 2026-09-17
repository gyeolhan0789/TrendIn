"""회귀 스냅샷 ([04 §9] · [09 §4]). 층 1 ([09 §4]).

`fixtures/corpus.json` 의 30건에 정제와 문서 안 추출을 돌려 `fixtures/snapshots.json` 과
대조한다. **품질을 재는 테스트가 아니다** — 재현성을 지킨다. 절대 수치는 사람이 매긴다
([04 §9]).

**모델을 부르지 않는다.** 인식 구간은 `fixtures/spans.json` 에 구워져 있고 여기서는 그
뒤의 계산만 다시 한다 — 트랜스포머 추론이 문턱 언저리에서 실행마다 흔들려 스냅샷이
경보가 아니라 잡음이 되기 때문이다 (`spark/scripts/update-snapshots.py` 의 주석).

결과가 바뀌면 실패한다. **의도한 변경이면 갱신하고 diff 를 커밋에 남긴다:**

    pipeline/.venv/Scripts/python.exe spark/scripts/update-snapshots.py

**픽스처가 파일 하나씩인 이유** — 문서마다 파일을 두면 코퍼스 30 + 스냅샷 30 으로
픽스처가 변경 목록의 절반을 넘고 정작 읽어야 할 구현·테스트가 묻힌다. 한 파일 안의
diff 는 git 이 지역적으로 보여 주므로 눈으로 보는 데 지장이 없다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPARK_DIR = Path(__file__).resolve().parents[2]
CORPUS = SPARK_DIR / "tests" / "fixtures" / "corpus.json"
SNAPSHOTS = SPARK_DIR / "tests" / "fixtures" / "snapshots.json"
SPANS = SPARK_DIR / "tests" / "fixtures" / "spans.json"
SCRIPT = SPARK_DIR / "scripts" / "update-snapshots.py"

HINT = "의도한 변경이면 `spark/scripts/update-snapshots.py` 로 갱신하고 diff 를 커밋에 남긴다"


def _load_script():
    """`update-snapshots.py` 는 하이픈이 든 스크립트라 import 문으로 못 읽는다. 계산을 두 곳에
    쓰지 않으려면 그 파일을 그대로 불러야 한다 — 테스트가 계산을 다시 구현하면 둘이 갈린다."""
    spec = importlib.util.spec_from_file_location("update_snapshots", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_snapshots"] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


CORPUS_DATA = _read(CORPUS)
SNAPSHOT_DATA = _read(SNAPSHOTS)
SPAN_DATA = _read(SPANS)
CASES = sorted(CORPUS_DATA)


def build(name: str) -> dict:
    """구간을 픽스처에서 읽어 그 뒤의 계산만 다시 한다."""
    return script.snapshot_for(
        CORPUS_DATA[name], script.load_config("local"), script.as_spans(SPAN_DATA.get(name, []))
    )


def test_코퍼스가_비어_있지_않다():
    """[04 §9] 가 정한 규모다. 30건은 눈으로 diff 를 볼 수 있는 상한이다 ([09 §4])."""
    assert len(CASES) == 30


def test_스냅샷과_코퍼스의_키가_짝이_맞는다():
    """코퍼스에 문서를 더하고 스냅샷을 만들지 않으면 여기서 걸린다."""
    assert sorted(SNAPSHOT_DATA) == CASES, HINT
    assert sorted(SPAN_DATA) == CASES, HINT


@pytest.mark.parametrize("name", CASES)
def test_추출_결과가_스냅샷과_같다(name):
    actual = build(name)

    assert actual == SNAPSHOT_DATA.get(name), f"{name} 의 추출 결과가 스냅샷과 다르다. {HINT}"


@pytest.mark.parametrize("name", CASES)
def test_같은_입력에_같은_결과다(name):
    """결정성 — 사전은 집합이고 후보 병합은 딕셔너리 순서에 기댄다. 두 번 돌려 같아야
    스냅샷이 의미를 갖는다 ([04 §9] "순서가 결정적이다").

    형태소 분석기가 들어온 뒤로 이 시험이 하나 더 지킨다 — **분석기가 상태를 들고 있지
    않다는 것.** 프로세스당 하나를 재사용하므로(`extract/morphology.analyzer_for`) 호출이
    앞의 호출에 영향을 받으면 배치 결과가 문서 순서에 따라 달라진다.
    """
    assert build(name) == build(name)


def test_축을_덮는다():
    """코퍼스는 **입력의 형태가 갈리는 축을 모두 덮게** 고른다 ([09 §4] 의 표).

    `api` · `dev` · `en` 축은 아직 표본이 없다 — `hn` 어댑터가 `S15P21A102-165` 대기 중이라
    dev 도메인 수집분이 0건이다 ([10 §5.1]). 그 어댑터가 붙으면 이 테스트가 먼저 빨개진다.
    """
    articles = [CORPUS_DATA[name] for name in CASES]
    routes = {article.get("route") for article in articles}
    assert {"rss", "listing"} <= routes

    empty = [a for a in articles if not (a.get("body_text") or "").strip()]
    assert len(empty) >= 3, "본문 없는 문서(회원 전용·빈 피드)가 셋 이상이어야 한다 ([03 §2])"

    assert {snap["normalize"]["basis"] for snap in SNAPSHOT_DATA.values()} >= {"body", "title"}

    # [03 §4] 단계 8 · [04 §2] · [04 §5] 의 회귀가 실제로 이 코퍼스에 들어 있는지.
    bodies = "\n".join(a.get("body_text") or "" for a in articles)
    assert "관련기사" in bodies, "위젯 절단 회귀가 코퍼스에 없다"
    assert "올가을" in bodies, "조사 규칙 회귀가 코퍼스에 없다"
