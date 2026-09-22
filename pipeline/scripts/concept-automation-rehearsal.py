#!/usr/bin/env python
"""`--auto-link` 를 켜면 무슨 일이 일어나는지 DB 없이 예행연습한다.

```sh
.venv/Scripts/python scripts/concept-automation-rehearsal.py \
  --input artifacts/live-unmapped.tsv
```

운영 작업과 같은 `run_workflow` 를 부르되 적재는 하지 않는다. 확인하는 것은 셋이다 —
네 결론이 어떻게 갈리는지, 같은 입력을 다시 넣었을 때 정말 묻지 않는지, 그리고 세지 않기로
판정된 표기가 순위에서 실제로 빠지는지.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.concept import workflow  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.judge import PROMPT_VERSION, Question  # noqa: E402
from trendin.spark.concept.retrieval import CandidateRetriever  # noqa: E402
from trendin.spark.io.llm import DEFAULT_MODEL, GmsClient  # noqa: E402
from trendin.spark.metrics.concepts import build_grouping  # noqa: E402

_live = importlib.util.spec_from_file_location(
    "_live_judge", ROOT / "scripts" / "concept-live-judge.py"
)
_live_judge = importlib.util.module_from_spec(_live)
_live.loader.exec_module(_live_judge)

POLICY = _live_judge.POLICY


class MemorySink:
    """`run_workflow` 가 기대하는 판정 캐시. 적재는 하지 않는다."""

    def __init__(self) -> None:
        self.values: dict[tuple, dict] = {}

    def cached_judgement(self, **key):
        return self.values.get(tuple(key.values()))

    def cache_judgement(self, *, verdict, **key):
        self.values[tuple(key.values())] = dict(verdict)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seed-dir", type=Path, default=ROOT / "spark" / "conf" / "concepts")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-calls", type=int, default=60)
    parser.add_argument("--dictionary-version", type=int, default=4)
    args = parser.parse_args(argv)

    rows = _live_judge.load_rows(args.input)
    dictionary = _live_judge._retrieval_script.seed_dictionary(args.seed_dir)
    retriever = CandidateRetriever(dictionary, CandidateIndex(dictionary), POLICY)
    _live_judge.load_key_from_env_file(ROOT / ".env")
    client = GmsClient(model=args.model)
    policy = workflow.AutomationPolicy(True, args.model, 20, args.max_calls, False)

    questions = [
        Question(
            index=index,
            lang=row["lang"],
            normalized=row["normalized"],
            article_count=row["articles"],
            context=row["context"],
            surface=row["surface"],
        )
        for index, row in enumerate(rows, start=1)
    ]

    print(f"── 1회차: 미등록 {len(questions)}건에 자동 판정을 켜고 돌린다")
    first = workflow.run_workflow(
        questions, client=client, cache=MemorySink(), retriever=retriever, policy=policy
    )
    print(
        f"   LLM 호출 {client.calls}회 · 연결 {len(first.links)}건 "
        f"· 유보 {len(first.deferred)}건"
    )
    tally = dict(Counter(d.decision for d in first.decisions))
    print(f"   판정 기록 {len(first.decisions)}건: {tally}")
    print(f"   기록하지 않은 일시적 실패: {len(first.deferred) - _durable(first)}건")

    settled = {
        d.key: d.decision
        for d in first.decisions
        if workflow.reusable(
            d.decision, PROMPT_VERSION, args.dictionary_version,
            prompt_version=PROMPT_VERSION, dictionary_version=args.dictionary_version,
        )
    }
    print(f"\n── 2회차: 같은 입력을 다시 넣는다 (지난 판정 {len(settled)}건을 안다)")
    before = client.calls
    second = workflow.run_workflow(
        questions, client=client, cache=MemorySink(), retriever=retriever,
        policy=policy, settled=settled,
    )
    print(f"   LLM 호출 {client.calls - before}회 · 건너뛴 표현 {len(second.reused)}건")
    print(f"   새로 내린 판정 {len(second.decisions)}건")

    silenced_keys = {d.key for d in first.decisions if d.decision == workflow.EXCLUDE}
    keyword_id = {question.key: index for index, question in enumerate(questions, start=1)}
    grouping = build_grouping(
        [], {}, keywords=set(keyword_id.values()),
        silenced_keywords=frozenset(keyword_id[key] for key in silenced_keys),
    )
    print(f"\n── 순위 반영: 세지 않기로 판정된 {len(grouping.silenced)}건이 순위에서 빠진다")
    by_id = {index: question for question, index in keyword_id.items()}
    shown = [by_id[i] for i in sorted(grouping.silenced)][:12]
    for lang, normalized in shown:
        print(f"   {lang} {normalized}")
    print(f"   토큰 합계 — 입력 {client.prompt_tokens} · 출력 {client.completion_tokens}")
    return 0


def _durable(result) -> int:
    return len([d for d in result.decisions if d.decision != workflow.LINK])


if __name__ == "__main__":
    raise SystemExit(main())
