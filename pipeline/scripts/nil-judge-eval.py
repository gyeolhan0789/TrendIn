#!/usr/bin/env python
"""덩이째 묻는 판정을 사람 검수 라벨로 잰다 (S15P21A102-386).

```sh
# 부르지 않고 견적만 본다.
.venv/Scripts/python scripts/nil-judge-eval.py clusters.jsonl --estimate

# 실제로 부른다. GMS_KEY 가 있어야 하고 크레딧이 든다.
GMS_KEY=... .venv/Scripts/python scripts/nil-judge-eval.py clusters.jsonl --out predictions.jsonl
```

입력은 덩이 한 줄에 하나인 JSONL 이다 — `registry/nil_candidates.clusters` 가 만든 덩이에 표기마다
등장 문장을 붙인 것.

```json
{"members":[{"key":"vogue world","surface":"Vogue World","kind":"컬렉션 또는 행사",
  "contexts":["..."]}],"pairs":[["vogue world","vogue world 2026",3]]}
```

라벨은 `spark/tests/fixtures/concept/nil-pairs-gold-*.jsonl` 이다 — 쌍마다 `S`(같은 대상) ·
`E`(같은 시리즈의 다른 회차) · `D`(다름) · `B`(정책에 따라 다름). `S`·`E` 를 "한 줄로 센다" 로
보고, 판정이 두 표기를 같은 묶음에 넣었는지로 채점한다. `B` 는 운영 기준으로 합치면 오류다. 덩이에
들지 못한 쌍은 묶지 않은 것으로 센다 — 후보 생성이 놓친 것도 재현율에 들어간다.

쌍 말고 **묶음 단위**로도 잰다 (`bad_group_rate`) — 합치는 쌍을 이으므로 틀린 쌍 하나가 묻지 않은
쌍까지 한 줄로 만든다. 저장해 둔 판정은 `--rescore` 로 다시 부르지 않고 채점만 한다.

```sh
.venv/Scripts/python scripts/nil-judge-eval.py clusters.jsonl --rescore predictions.jsonl
```
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.concept.cluster_judge import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    EXAMPLE_PAIRS,
    MODEL,
    PROMPT_VERSION,
    Cluster,
    Judgement,
    Member,
    _fold,
    batches,
    merged_groups,
    merged_pairs,
    messages,
    parse,
)
from trendin.spark.concept.judge import estimate_tokens  # noqa: E402
from trendin.spark.io.llm import GmsClient  # noqa: E402

DEFAULT_GOLD = ROOT / "spark/tests/fixtures/concept/nil-pairs-gold-2026-09-24.jsonl"
MERGE_LABELS = {"S": "same", "E": "series"}
# 쌍 하나의 답 출력 토큰 어림. `{"n":1,"p":1,"rel":"narrower"}` 가 열다섯 남짓이다.
OUTPUT_TOKENS_PER_PAIR = 16


def load_clusters(path: Path) -> list[Cluster]:
    clusters = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        members = tuple(
            Member(m["key"], m["surface"], m.get("kind"), tuple(m.get("contexts") or ()))
            for m in row["members"]
        )
        pairs = tuple((a, b, int(n)) for a, b, n in row["pairs"])
        clusters.append(Cluster(members, pairs))
    return clusters


def max_tokens(batch: list[Cluster]) -> int:
    return 100 + 2 * OUTPUT_TOKENS_PER_PAIR * sum(len(c.pairs) for c in batch)


def ask(client: GmsClient, batch: list[Cluster]) -> tuple[list[Judgement | None], list[str], int]:
    """묶어서 묻고, 어긋난 덩이만 하나씩 한 번 더 묻는다. 부른 횟수도 돌려준다."""
    content = client.chat(messages(batch), max_tokens=max_tokens(batch))
    judgements, problems = parse(content, batch)
    calls = 1
    for i, judgement in enumerate(judgements):
        if judgement is None:
            single = [batch[i]]
            content = client.chat(messages(single), max_tokens=max_tokens(single))
            retry, retry_problems = parse(content, single)
            calls += 1
            judgements[i] = retry[0]
            problems += retry_problems
    return judgements, problems, calls


# 지시문에 예로 든 쌍 — 채점에서 뺀다. 답을 보여 주고 채점하는 셈이라서다. 비교하는 판정들은
# **같은 쌍을 빼고** 채점해야 공정하다 (`--rescore` 도 같은 목록을 뺀다).
EXCLUDED = frozenset(frozenset((_fold(a), _fold(b))) for a, b in EXAMPLE_PAIRS)


def score(gold_path: Path, clusters: list[Cluster], judgements: list[Judgement | None]) -> dict:
    key_of = {m.surface: m.key for c in clusters for m in c.members}
    merged: dict[tuple[str, str], str] = {}
    groups: list[tuple[str, ...]] = []
    unsure = 0
    for judgement in judgements:
        if judgement is not None:
            merged |= merged_pairs(judgement)
            groups += [keys for keys, _ in merged_groups(judgement)]
            unsure += sum(1 for r in judgement.relations.values() if r == "unsure")

    labels: dict[tuple[str, str], str] = {}
    tp = fp = fn = tn = relation_ok = excluded = 0
    mistakes: list[str] = []
    for line in gold_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if frozenset((_fold(row["short"]), _fold(row["long"]))) in EXCLUDED:
            excluded += 1
            continue
        a, b = key_of.get(row["short"]), key_of.get(row["long"])
        pair = tuple(sorted((a, b))) if a and b else None
        if pair:
            labels[pair] = row["label"]
        predicted = merged.get(pair) if pair else None
        # 운영 기준 — 정책이 안 정해진 `B` 는 합치면 오류다. 연구용으로 빼면 실제 위험을 놓친다.
        expected = MERGE_LABELS.get(row["label"])
        if expected and predicted:
            tp += 1
            relation_ok += expected == predicted
        elif expected:
            fn += 1
            mistakes.append(f"놓침 {row['label']}  {row['short']} | {row['long']}")
        elif predicted:
            fp += 1
            mistakes.append(f"잘못 묶음 ({predicted})  {row['short']} | {row['long']}")
        else:
            tn += 1

    # 묶음 단위 — 잇기 때문에 틀린 쌍 하나가 묶음 전체를 오염시킨다. 묶음 안의 어느 쌍이든
    # 합치면 안 되는 라벨(`D` · `B`)이면 나쁜 묶음이다. 라벨이 없는 쌍은 모른다.
    bad = []
    for keys in groups:
        pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1 :]]
        if any(labels.get(pair) in ("D", "B") for pair in pairs):
            bad.append(keys)
    mistakes += [f"나쁜 묶음  {' / '.join(keys)}" for keys in bad]
    return {
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "relation_agreement": round(relation_ok / tp, 3) if tp else None,
        "excluded_example_pairs": excluded,
        "groups": len(groups),
        "bad_group_rate": round(len(bad) / len(groups), 3) if groups else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "unsure_pairs": unsure,
        "failed_clusters": sum(1 for j in judgements if j is None),
        "mistakes": mistakes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clusters", type=Path)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-calls", type=int, default=100, help="요청이 이보다 많으면 멈춘다")
    parser.add_argument("--estimate", action="store_true", help="부르지 않고 견적만 본다")
    parser.add_argument("--out", type=Path, default=None, help="덩이별 판정을 JSONL 로 남긴다")
    parser.add_argument("--rescore", type=Path, default=None, help="저장한 판정을 채점만 한다")
    args = parser.parse_args(argv)

    clusters = load_clusters(args.clusters)
    if args.rescore:
        return report(args.gold, clusters, load_predictions(args.rescore, clusters))
    requests = batches(clusters, args.batch_size)
    tokens = sum(estimate_tokens(m["content"]) for b in requests for m in messages(b))
    pairs = sum(len(c.pairs) for c in clusters)
    print(
        f"덩이 {len(clusters)} · 요청 {len(requests)} · 입력 어림 {tokens:,} 토큰 · "
        f"출력 어림 {OUTPUT_TOKENS_PER_PAIR * pairs:,} 토큰",
        file=sys.stderr,
    )
    if args.estimate:
        return 0
    if len(requests) > args.max_calls:
        print(f"요청이 --max-calls({args.max_calls}) 보다 많다", file=sys.stderr)
        return 2

    client = GmsClient(model=args.model)
    judgements: list[Judgement | None] = []
    rows: list[dict] = []
    calls = 0
    for n, batch in enumerate(requests, start=1):
        answers, problems, used = ask(client, batch)
        calls += used
        judgements += answers
        if problems:
            print(f"[요청 {n}] {problems}", file=sys.stderr)
        for cluster, judgement in zip(batch, answers):
            relations = judgement.relations.items() if judgement else ()
            rows.append(
                {
                    "members": [m.key for m in cluster.members],
                    "relations": [[a, b, r] for (a, b), r in relations] if judgement else None,
                }
            )
    print(f"{PROMPT_VERSION} · 실제 요청 {calls} 회 (다시 물은 것 포함)", file=sys.stderr)
    if args.out:
        lines = (json.dumps(row, ensure_ascii=False) for row in rows)
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return report(args.gold, clusters, judgements)


def load_predictions(path: Path, clusters: list[Cluster]) -> list[Judgement | None]:
    """`--out` 이 남긴 판정 → 덩이 순서대로. 덩이는 구성원으로 맞춘다."""
    by_members: dict[tuple[str, ...], Judgement | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        relations = row["relations"]
        judgement = Judgement({(a, b): r for a, b, r in relations}) if relations else None
        by_members[tuple(row["members"])] = judgement
    return [by_members.get(tuple(m.key for m in c.members)) for c in clusters]


def report(gold: Path, clusters: list[Cluster], judgements: list[Judgement | None]) -> int:
    result = score(gold, clusters, judgements)
    mistakes = result.pop("mistakes")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for line in mistakes:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
