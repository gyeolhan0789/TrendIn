#!/usr/bin/env python
"""사전을 바꾸기 전후의 `--dump` 두 장을 맞대 **무엇이 어디로 갔는지** 센다.

```sh
spark/scripts/submit.sh concept --profile dev --domain fashion --dry-run \
    --seed-in-memory --dump /tmp/before.jsonl     # 사전 파일을 바꾸기 전
#   ... spark/conf/concepts/ 에 새 출처를 넣고 ...
spark/scripts/submit.sh concept --profile dev --domain fashion --dry-run \
    --seed-in-memory --dump /tmp/after.jsonl      # 바꾼 뒤

.venv/Scripts/python scripts/concept-dump-diff.py /tmp/before.jsonl /tmp/after.jsonl
```

**매핑률만 보면 안 되기 때문에 있는 것이다.** 표현을 늘리면 없던 표기가 붙기도 하지만
(`unmapped → resolved`), 같은 표기가 두 개념에 걸리면서 **원래 붙던 것이 모호해져 밀려나기도**
한다 (`resolved → deferred`). 둘이 상쇄되면 매핑률은 그대로인데 품질은 나빠진 것이다.
그래서 합계가 아니라 이동을 센다.

세는 단위는 `(기사, 언어, 비교키)` 다. 한 표기는 `resolved` · `context` · `deferred` ·
`unmapped` 중 정확히 하나이므로 이동 표의 합은 표기 수와 같다. `context` 는 모호했지만 문맥
규칙이 갈라 붙인 것이라 **붙은 쪽으로 센다** — 다만 `resolved → context` 는 따로 "모호해짐"
으로 세어, 붙기는 계속 붙어도 사전이 지저분해진 것을 놓치지 않는다.

`-` 는 그 실행에 아예 없던 표기다 — 두 덤프를 다른 창이나 다른 날에 떴다는 뜻이고, 그 줄이
크면 비교 자체가 성립하지 않는다.

**개념 번호 비교는 양쪽이 `--seed-in-memory` 가 아닐 때만 한다.** 메모리 사전의 새 개념은
음수라 두 실행에서 같은 번호가 아니다 (`jobs/concept.py` 의 `_dump`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# 이 스크립트는 컨테이너가 아니라 사람 노트북에서 돌린다. 윈도 콘솔 기본 인코딩(cp949)이
# 표에 쓰는 문자를 못 찍어 죽는 것을 막는다 — 표가 읽히는 것이 이 도구의 전부다.
for _stream in (sys.stdout, sys.stderr):
    if (_stream.encoding or "").lower().replace("-", "") != "utf8":
        _stream.reconfigure(encoding="utf-8", errors="replace")

OUTCOMES = ("resolved", "context", "deferred", "unmapped")
# 기사에 개념이 남는 상태. `context` 는 모호했지만 문맥 규칙이 갈라 붙인 것이라 붙은 쪽이다 —
# 다만 `resolved` 보다 약하다. 회귀는 "붙던 것이 안 붙게 됐다" 로 센다.
ATTACHING = frozenset({"resolved", "context"})
MISSING = "-"
ORDER = [MISSING, *OUTCOMES]


def read(path: Path) -> tuple[dict, dict[tuple, str], dict[int, set[int]]]:
    """덤프 한 장 → (meta, 표기별 결과, 개념별 기사 집합)."""
    meta: dict = {}
    surfaces: dict[tuple, str] = {}
    concepts: dict[int, set[int]] = defaultdict(set)
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        kind = record.get("t")
        if kind == "meta":
            meta = record
        elif kind in OUTCOMES:
            key = (record["article_id"], record["lang"], record["normalized"])
            if key in surfaces:
                raise ValueError(f"{path}:{number}: 같은 표기가 두 번 — 덤프가 깨졌다: {key}")
            surfaces[key] = kind
        elif kind == "row":
            concepts[record["concept_id"]].add(record["article_id"])
        else:
            raise ValueError(f"{path}:{number}: 모르는 줄 종류: {kind!r}")
    if not meta:
        raise ValueError(f"{path}: meta 줄이 없다 — --dump 가 만든 파일이 맞나")
    return meta, surfaces, dict(concepts)


def delta(before: int, after: int) -> str:
    return f"{before:,} → {after:,} ({after - before:+,})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--examples", type=int, default=5,
                        help="이동한 표기 예시를 종류마다 이만큼 보여준다. 0 이면 끔")
    parser.add_argument("--json", action="store_true", help="표 대신 JSON 하나로 찍는다")
    parser.add_argument("--fail-on-regression", action="store_true",
                        help="회귀가 하나라도 있으면 1 로 끝난다. CI 관문용")
    args = parser.parse_args(argv)
    if args.examples < 0:
        parser.error("--examples 는 0 이상이어야 한다")

    before_meta, before, before_concepts = read(args.before)
    after_meta, after, after_concepts = read(args.after)
    for field in ("domain", "window_days"):
        if before_meta.get(field) != after_meta.get(field):
            print(
                f"⚠ {field} 가 다르다: {before_meta.get(field)!r} 대 {after_meta.get(field)!r} "
                "— 같은 조건이 아니면 이동 수를 믿을 수 없다",
                file=sys.stderr,
            )

    moves: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    for key in set(before) | set(after):
        move = (before.get(key, MISSING), after.get(key, MISSING))
        moves[move] += 1
        if len(examples[move]) < args.examples:
            examples[move].append(key)

    # 말뭉치가 달라져 한쪽에만 있는 표기는 회귀도 개선도 아니다. 창이 하루만 밀려도 수백 건이
    # 생기므로, 먼저 갈라내지 않으면 회귀 수가 통째로 거짓이 된다.
    regressions = sum(
        n for (a, b), n in moves.items()
        if a in ATTACHING and b in OUTCOMES and b not in ATTACHING
    )
    improvements = sum(
        n for (a, b), n in moves.items()
        if b in ATTACHING and a in OUTCOMES and a not in ATTACHING
    )
    # 붙기는 계속 붙지만 근거가 약해진 것. 회귀는 아니어도 사전이 지저분해졌다는 신호다.
    weakened = moves.get(("resolved", "context"), 0)
    drifted = sum(n for (a, b), n in moves.items() if MISSING in (a, b))

    # 개념 번호는 메모리 사전에서 음수라 두 실행에서 같은 것을 가리키지 않는다.
    comparable = not (before_meta.get("seed_in_memory") or after_meta.get("seed_in_memory"))
    lost_concepts = sorted(set(before_concepts) - set(after_concepts)) if comparable else []
    gained_concepts = sorted(set(after_concepts) - set(before_concepts)) if comparable else []

    if args.json:
        print(json.dumps(
            {
                "before": before_meta,
                "after": after_meta,
                "moves": {f"{a}->{b}": n for (a, b), n in sorted(moves.items())},
                "regressions": regressions,
                "improvements": improvements,
                "weakened": weakened,
                "drifted": drifted,
                "concepts_comparable": comparable,
                "concepts_lost": lost_concepts,
                "concepts_gained": gained_concepts,
            },
            ensure_ascii=False, indent=2, sort_keys=True,
        ))
        return 1 if args.fail_on_regression and regressions else 0

    if before_meta.get("seed_dir") != after_meta.get("seed_dir"):
        print(f"사전    {before_meta.get('seed_dir')}")
        print(f"     →  {after_meta.get('seed_dir')}")
    print(f"개념    {delta(before_meta['concepts'], after_meta['concepts'])}")
    print(f"표현    {delta(before_meta['expressions'], after_meta['expressions'])}")
    print(f"기사    {delta(before_meta['articles'], after_meta['articles'])}")
    print(f"표기    {delta(len(before), len(after))}")
    print(f"개념 행 {delta(before_meta['rows'], after_meta['rows'])}")

    print("\n표기 결과 이동")
    for source in ORDER:
        for target in ORDER:
            count = moves.get((source, target), 0)
            if not count:
                continue
            if MISSING in (source, target):
                mark = "  ← 말뭉치가 달라졌다"
            elif source in ATTACHING and target not in ATTACHING:
                mark = "  ← 회귀"
            elif target in ATTACHING and source not in ATTACHING:
                mark = "  ← 좋아짐"
            elif (source, target) == ("resolved", "context"):
                mark = "  ← 모호해졌다 (붙긴 붙는다)"
            elif (source, target) == ("context", "resolved"):
                mark = "  ← 또렷해졌다"
            else:
                mark = ""
            print(f"  {source:9} → {target:9} {count:6,}{mark}")
            for article_id, lang, normalized in examples[(source, target)]:
                if source != target:
                    print(f"      기사 {article_id} · {lang} · {normalized}")

    print(
        f"\n회귀 {regressions:,} · 좋아짐 {improvements:,} · "
        f"모호해짐 {weakened:,} · 말뭉치 차이 {drifted:,}"
    )
    if not comparable:
        print("개념 번호 비교는 건너뛴다 — 메모리 사전의 새 개념은 음수라 짝이 맞지 않는다")
    elif lost_concepts or gained_concepts:
        print(f"개념 단위: 사라짐 {len(lost_concepts):,} · 새로 붙음 {len(gained_concepts):,}")
    if regressions:
        print("\n원래 붙던 표기가 밀려났다. 모호해진 것인지 확인하고, 맞으면 그 출처를 되돌린다.")
    return 1 if args.fail_on_regression and regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
