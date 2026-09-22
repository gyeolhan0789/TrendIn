#!/usr/bin/env python
"""운영 DB 에서 뽑은 실제 미등록 표기에 2단계 판정을 돌린다.

```sh
.venv/Scripts/python scripts/concept-live-judge.py \
  --input artifacts/live-unmapped.tsv --output artifacts/live-judge.jsonl
```

골드셋과 달리 정답 라벨이 없다. 무엇이 맞았는지가 아니라 **무엇으로 갈렸는지**를 본다 —
기존 개념에 붙일 것(LINK), 새로 넣을 것(NEW), 세지 않을 것(EXCLUDE), 사람에게 넘길 것(DEFER).
입력 표기는 사전에 없는 것들이므로 누설 차단이 필요 없다.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.concept import vector_judge  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.judge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    UNCOUNTED,
    NameIndex,
    Question,
    batches,
    messages,
    parse,
    usable_context,
)
from trendin.spark.concept.retrieval import CandidateRetriever, RetrievalPolicy  # noqa: E402
from trendin.spark.io.llm import DEFAULT_MODEL, GmsClient  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_quality_retrieval", ROOT / "scripts" / "concept-quality-retrieval.py"
)
_retrieval_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_retrieval_script)

POLICY = RetrievalPolicy(
    top_k=5,
    min_combined_score=0.55,
    meaningful_candidate_threshold=0.5,
    category_mismatch_factor=0.25,
    consensus_bonus=0.05,
    thresholds={"exact": 1.0, "normalized": 1.0, "character": 0.8, "phonetic": 0.8, "vector": 0.7},
    weights={"exact": 1.0, "normalized": 0.95, "character": 0.8, "phonetic": 0.85, "vector": 0.85},
)


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", newline="") as stream:
        # psql 머리말에 큰따옴표가 들어 있어 따옴표 해석을 끈다. 켜 두면 그 줄이 파일 전체를
        # 한 칸으로 삼켜 한 건도 읽히지 않는다.
        for line in csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(line) < 4 or not line[0] or not line[3].strip().isdigit():
                continue
            rows.append(
                {
                    "lang": line[0],
                    "normalized": line[1],
                    "surface": line[2] or line[1],
                    "articles": int(line[3] or 0),
                    "context": line[4] if len(line) > 4 else "",
                }
            )
    return rows


def load_key_from_env_file(path: Path) -> None:
    if os.environ.get("GMS_KEY") or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "GMS_KEY" and value.strip():
            os.environ["GMS_KEY"] = value.strip().strip("'\"")
            return


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed-dir", type=Path, default=ROOT / "spark" / "conf" / "concepts")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--vectors", action="store_true", help="로컬 임베딩 후보를 섞는다")
    args = parser.parse_args(argv)

    rows = load_rows(args.input)
    if args.limit:
        rows = rows[: args.limit]
    dictionary = _retrieval_script.seed_dictionary(args.seed_dir)
    retriever = CandidateRetriever(dictionary, CandidateIndex(dictionary), POLICY)
    names = NameIndex(dictionary)
    load_key_from_env_file(ROOT / ".env")
    client = GmsClient(model=args.model)
    vector_search = None
    if args.vectors:
        spec = importlib.util.spec_from_file_location(
            "_local_vectors", ROOT / "artifacts" / "local_vectors.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        vector_search = module.LocalVectorSearch(dictionary, top_k=POLICY.top_k)

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

    verdicts = {}
    started = time.perf_counter()
    for group in batches(questions, args.batch_size):
        answers, trouble = parse(client.chat(messages(group)), group)
        for problem in trouble:
            print(f"  ! {problem}", file=sys.stderr)
        for verdict in answers:
            verdicts[verdict.normalized] = verdict
    naming_ms = (time.perf_counter() - started) * 1000 / max(len(questions), 1)

    out = []
    for row in rows:
        verdict = verdicts.get(row["normalized"])
        if verdict is None:
            out.append({**row, "decision": "DEFER", "reason": "NAME_FAILED"})
            continue
        if verdict.category in UNCOUNTED:
            out.append(
                {**row, "decision": "EXCLUDE", "english_name": verdict.english_name,
                 "verdict_category": verdict.category, "path": "generic", "gate": None}
            )
            continue
        hits = (
            vector_search(row["surface"], verdict.english_name) if vector_search else {}
        )
        result = retriever.retrieve(
            original=row["surface"],
            lang=row["lang"],
            english_name=verdict.english_name,
            category=verdict.category,
            vector_hits=hits,
        )
        candidates = result.candidates
        exact = (
            names.exact_link(verdict.english_name, verdict.category)
            if usable_context(row["context"], row["surface"], row["normalized"])
            else None
        )
        path = "exact" if exact is not None else "none"
        choice = gate = None
        exhausted = False
        # 운영과 같은 순서다. 1위가 문턱에 못 미치면 검색기가 이미 유보로 표시하므로 LLM 을
        # 부르지 않는다. 이걸 빠뜨리면 점수 0.2 짜리 잡음 후보에도 돈을 쓴다.
        if result.deferred:
            gate = result.defer_reason or "NO_CANDIDATE"
        elif exact is None and candidates:
            path = "verify"
            try:
                choice = vector_judge.parse_choice(
                    client.chat(vector_judge.messages(verdict, candidates, context=row["context"])),
                    candidates,
                )
            except ValueError as error:
                print(f"  ! {row['normalized']}: {error}", file=sys.stderr)
            gate = vector_judge.rejection_reason(
                verdict, candidates, choice,
                min_similarity=POLICY.min_combined_score, context=row["context"],
            )
            exhausted = bool(choice is not None and choice.exhausted)
            choice = None if gate is not None else choice.concept_id
        concept_id = exact if exact is not None else choice
        if concept_id is not None:
            concept = dictionary.concept(concept_id)
            decision, linked = "LINK", concept.canonical_name
        elif result.no_match or exhausted:
            # 후보가 잡음 수준이거나, 후보를 다 보고 "이 중에 없다" 고 한 것이다. 둘 다 사람이
            # 아니라 신규 개념 경로로 간다.
            decision, linked = "NEW", None
        else:
            decision, linked = "DEFER", None
        out.append(
            {
                **row,
                "decision": decision,
                "concept": linked,
                "english_name": verdict.english_name,
                "verdict_category": verdict.category,
                "path": path,
                "gate": gate,
                "candidates": [
                    {"name": item.name, "category": item.category, "score": item.score}
                    for item in candidates[:3]
                ],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for item in out:
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"표현 {len(out)}건, 호출 {client.calls}회, "
          f"입력 {client.prompt_tokens} · 출력 {client.completion_tokens} 토큰, "
          f"이름판정 평균 {naming_ms:.0f}ms")
    print("결정:", dict(Counter(item['decision'] for item in out)))
    print("경로:", dict(Counter(item.get('path') for item in out)))
    print("관문:", dict(Counter(item.get('gate') for item in out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
