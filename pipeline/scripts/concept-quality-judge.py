#!/usr/bin/env python
"""골드셋에 운영과 같은 2단계 LLM 판정을 돌려 예측 JSONL 을 만든다.

```sh
# 부르지 않고 배선만 확인한다 (크레딧 0).
.venv/Scripts/python scripts/concept-quality-judge.py --dry-run --output artifacts/dry.jsonl

# 실제로 부른다. GMS_KEY 가 있어야 하고 크레딧이 든다.
GMS_KEY=... .venv/Scripts/python scripts/concept-quality-judge.py --output artifacts/judge.jsonl
```

운영 순서를 그대로 따른다 — 후보를 보여 주지 않고 영어 이름·분류부터 묻고, 그 이름으로 사전을
조회하고, 정확 일치가 없을 때만 후보를 보여 주며 같은 대상인지 되묻는다. DB 는 쓰지 않는다.

한 번 부르고 두 실험을 적는다. `llm-judge-raw` 는 모델 판단 그대로이고,
`llm-judge-gated` 는 운영 자동 반영 관문(`vector_judge.eligible_choice`)을 통과한 것만
LINK 로 적는다. 관문이 실제로 무엇을 막는지 추가 비용 없이 같이 재려는 것이다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.concept import vector_judge  # noqa: E402
from trendin.spark.concept.candidates import CandidateIndex  # noqa: E402
from trendin.spark.concept.evaluation import load_gold  # noqa: E402
from trendin.spark.concept.judge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    UNCOUNTED,
    NameIndex,
    Question,
    Verdict,
    batches,
    messages,
    parse,
    usable_context,
)
from trendin.spark.concept.normalize import concept_key  # noqa: E402
from trendin.spark.concept.retrieval import CandidateRetriever, RetrievalPolicy  # noqa: E402
from trendin.spark.io.llm import DEFAULT_MODEL, GmsClient  # noqa: E402

DEFAULT_GOLD = ROOT / "spark" / "tests" / "fixtures" / "concept" / "quality-gold-v1.jsonl"
DEFAULT_SEEDS = ROOT / "spark" / "conf" / "concepts"

_spec = importlib.util.spec_from_file_location(
    "_quality_retrieval", ROOT / "scripts" / "concept-quality-retrieval.py"
)
_retrieval_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_retrieval_script)

# base.yaml 의 concept.retrieval 과 같은 값이다. DB 없이 돌리므로 여기 적는다.
POLICY = RetrievalPolicy(
    top_k=5,
    min_combined_score=0.55,
    meaningful_candidate_threshold=0.5,
    category_mismatch_factor=0.25,
    consensus_bonus=0.05,
    thresholds={"exact": 1.0, "normalized": 1.0, "character": 0.8, "phonetic": 0.8, "vector": 0.7},
    weights={"exact": 1.0, "normalized": 0.95, "character": 0.8, "phonetic": 0.85, "vector": 0.85},
)


class FakeClient:
    """크레딧 없이 배선을 확인한다. 이름은 골드의 정답을, 검증은 1순위 후보를 돌려준다."""

    model = "fake"

    def __init__(self, gold) -> None:
        self.by_key = {concept_key(case.surface): case for case in gold}
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def chat(self, msgs: list[dict[str, str]], *, max_tokens: int = 1200) -> str:
        self.calls += 1
        self.prompt_tokens += 300
        self.completion_tokens += 40
        payload = json.loads(msgs[1]["content"])
        if "items" in payload:
            rows = [
                {
                    "i": item["i"],
                    "en": self.by_key[item["w"]].english_name or item["w"],
                    "cat": self.by_key[item["w"]].category,
                }
                for item in payload["items"]
            ]
            return json.dumps({"r": rows})
        candidates = payload.get("candidates") or []
        return json.dumps({"concept_id": candidates[0]["concept_id"] if candidates else None})


def load_key_from_env_file(path: Path) -> None:
    """`pipeline/.env` 의 GMS_KEY 를 환경변수로 올린다 — 키가 명령줄에 남지 않게 한다."""
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
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--seed-dir", type=Path, default=DEFAULT_SEEDS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="LLM 을 부르지 않는다")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    gold = load_gold(args.gold)
    dictionary = _retrieval_script.seed_dictionary(args.seed_dir)
    retriever = CandidateRetriever(dictionary, CandidateIndex(dictionary), POLICY)
    names = NameIndex(dictionary)
    expressions = list(dictionary.expressions())
    if not args.dry_run:
        load_key_from_env_file(ROOT / ".env")
    client = FakeClient(gold) if args.dry_run else GmsClient(model=args.model)

    questions = [
        Question(
            index=index,
            lang=case.language,
            normalized=concept_key(case.surface),
            article_count=1,
            context=case.context,
            surface=case.surface,
        )
        for index, case in enumerate(gold, start=1)
    ]

    verdicts: dict[str, Verdict] = {}
    naming_tokens: dict[str, tuple[int, int]] = {}
    problems: list[str] = []
    started = time.perf_counter()
    for group in batches(questions, args.batch_size):
        before = (client.prompt_tokens, client.completion_tokens)
        answers, trouble = parse(client.chat(messages(group)), group)
        # 배치 한 번의 토큰을 그 배치 인원으로 나눠 붙인다. 표현당 비용을 재려면 합계만으로는
        # 모자라고, 뒤에 이어지는 검증 호출과 섞이지 않게 여기서 떼어 놓아야 한다.
        share = (
            (client.prompt_tokens - before[0]) // max(len(group), 1),
            (client.completion_tokens - before[1]) // max(len(group), 1),
        )
        problems.extend(trouble)
        for verdict in answers:
            verdicts[verdict.normalized] = verdict
            naming_tokens[verdict.normalized] = share
    naming_ms = (time.perf_counter() - started) * 1000 / max(len(questions), 1)
    if problems:
        print(f"이름 판정에서 읽지 못한 항목 {len(problems)}건: {problems[:5]}", file=sys.stderr)

    rows: list[dict] = []
    namer_name_ok = namer_category_ok = namer_total = 0
    for case in gold:
        key = concept_key(case.surface)
        verdict = verdicts.get(key)
        if verdict is None:
            for experiment in ("llm-judge-raw", "llm-judge-gated"):
                rows.append(
                    _row(case, experiment, "DEFER", None, None, (), naming_ms, 1,
                         verdict=None, path="none", gate="NAME_FAILED", tokens=(0, 0))
                )
            continue
        if case.english_name:
            namer_total += 1
            namer_name_ok += _same(verdict.english_name, case.english_name)
            namer_category_ok += verdict.category == case.category

        case_started = time.perf_counter()
        excluded = frozenset(
            expression.expression_id
            for expression in expressions
            if expression.normalized == key
        )
        result = retriever.retrieve(
            original=case.surface,
            lang=case.language,
            english_name=verdict.english_name,
            category=verdict.category,
            vector_hits={},
            exclude_expression_ids=excluded,
        )
        candidates = result.candidates
        calls = 1
        raw_choice = None
        gate = None
        before = (client.prompt_tokens, client.completion_tokens)
        # 정확 일치도 문맥이 있어야 잇는다 (`auto_link.select_links` 와 같은 규칙).
        exact = (
            names.exact_link(verdict.english_name, verdict.category)
            if verdict.category not in UNCOUNTED
            and usable_context(case.context, case.surface, key, verdict.english_name)
            else None
        )
        path = "exact" if exact is not None else "none"
        if exact is None and candidates and verdict.category not in UNCOUNTED:
            path = "verify"
            content = client.chat(vector_judge.messages(verdict, candidates, context=case.context))
            calls += 1
            try:
                raw_choice = vector_judge.parse_choice(content, candidates)
            except ValueError as error:
                print(f"{case.case_id}: 검증 답을 못 읽었다 — {error}", file=sys.stderr)
        # 어느 관문이 막았는지 그대로 적는다. 관문이 실제로 무엇을 거르는지는 이 값을 세어야 안다.
        # 정확 일치로 끝난 표현에는 관문이 붙지 않으므로 비워 둔다 — 빈칸 자체가 우회의 기록이다.
        if path == "verify":
            gate = vector_judge.rejection_reason(
                verdict,
                candidates,
                raw_choice,
                min_similarity=POLICY.min_combined_score,
                context=case.context,
            )
        exhausted = bool(raw_choice is not None and raw_choice.exhausted)
        picked = raw_choice.concept_id if raw_choice is not None else None
        gated_choice = None if gate is not None else picked
        elapsed = (time.perf_counter() - case_started) * 1000 + naming_ms
        naming_share = naming_tokens.get(key, (0, 0))
        tokens = (
            naming_share[0] + client.prompt_tokens - before[0],
            naming_share[1] + client.completion_tokens - before[1],
        )

        for experiment, choice in (
            ("llm-judge-raw", picked),
            ("llm-judge-gated", gated_choice),
        ):
            decision, concept, category = _decide(
                verdict, result, exact, choice, dictionary, exhausted
            )
            rows.append(
                _row(case, experiment, decision, concept, category, candidates, elapsed, calls,
                     verdict=verdict, path=path, gate=gate, tokens=tokens)
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    print(
        f"호출 {client.calls}회, 입력 {client.prompt_tokens} 토큰, "
        f"출력 {client.completion_tokens} 토큰"
    )
    if namer_total:
        print(
            f"영어명 정확도 {namer_name_ok}/{namer_total} = {namer_name_ok / namer_total:.1%}, "
            f"분류 정확도 {namer_category_ok}/{namer_total} = "
            f"{namer_category_ok / namer_total:.1%}"
        )
    print(f"예측 {len(rows)}행 -> {args.output}")
    return 0


def _decide(verdict, result, exact, choice, dictionary, exhausted=False):
    """운영 규칙 그대로 최종 행동을 정한다 — generic 은 세지 않고, 정확 일치가 검증보다 앞선다.

    후보가 **나왔는지**가 아니라 **의미 있는지**로 신규와 유보를 가른다. 소리만 닮은 0.19 짜리
    후보는 애매하다는 뜻이 아니라 없다는 뜻이다.
    """
    if verdict.category in UNCOUNTED:
        return "EXCLUDE", None, None
    concept_id = exact if exact is not None else choice
    if concept_id is not None:
        concept = dictionary.concept(concept_id)
        return "LINK", concept.canonical_name, concept.category
    if result.no_match or exhausted:
        return "NEW", None, None
    return "DEFER", None, None


def _row(case, experiment, decision, concept, category, candidates, elapsed_ms, calls,
         *, verdict, path, gate, tokens):
    """한 표현의 결과 한 줄. 판정과 경로까지 적어야 실행을 다시 부르지 않고 따져 볼 수 있다."""
    return {
        "case_id": case.case_id,
        "experiment": experiment,
        "decision": decision,
        "concept": concept,
        "category": category,
        "english_name": verdict.english_name if verdict else None,
        "verdict_category": verdict.category if verdict else None,
        "path": path,
        "gate": gate,
        "candidates": [
            {
                "name": item.name,
                "category": item.category,
                "score": item.score,
                "evidence_score": getattr(item, "evidence_score", item.score),
            }
            for item in candidates
        ],
        "elapsed_ms": round(elapsed_ms, 3),
        "llm_calls": calls,
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
    }


def _same(left: str | None, right: str | None) -> bool:
    def key(value: str | None) -> str:
        return " ".join((value or "").casefold().replace("-", " ").split())

    return key(left) == key(right)


if __name__ == "__main__":
    raise SystemExit(main())
