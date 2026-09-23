#!/usr/bin/env python
"""미등록 표현 검수 — TSV 한 장으로 내보내고, 결정을 적어 되돌려 넣는다.

```sh
.venv/Scripts/python scripts/concept-review.py export --profile local > review.tsv
#   ... review.tsv 의 decision 열을 채운다 ...
.venv/Scripts/python scripts/concept-review.py apply  --profile local review.tsv --by human:jk
```

MVP 에서 관리 화면 대신 쓰는 것이다. 하루 검수량이 수십 건이면 이걸로 충분하고, 사람이 파일로
못 따라갈 때 화면을 만든다 (2026-09-17 설계 §2).

## 관찰 모드의 제안이 미리 채워진다

`concept.automation.enabled` 는 켜고 `apply_links` 는 잠근 상태로 돌면, 판정이 사전에 들어가지
않고 `pl_concept_unmapped.proposal` 에 제안으로 쌓인다 (S15P21A102-363). `export` 는 그 제안을
`decision`·`concept` 열에 미리 적고, 왜 그렇게 봤는지를 `why` 열에 남긴다.

**손대지 않은 줄은 제안대로 반영된다.** `apply` 는 `decision` 이 적힌 줄을 전부 실행하므로,
훑지 않고 그대로 넣으면 자동 반영을 켠 것과 같아진다. 아니라고 보는 줄은 고치거나 비운다.
`DEFER` 와 모양이 어긋난 제안은 애초에 비워서 나간다.

## 내보내는 표

```
lang  normalized  surface  articles  contexts               decision  concept  note
ja    ばれえこあ    バレエコア  7         「バレエコア」がSNSで… ⏎ …
ko    느낌         느낌       41        …
```

`articles` 가 많은 것부터다 — 영향이 큰 것부터 본다. `contexts` 는 표본 세 개를 ` ⏎ ` 로 이었다.

## 결정 열

| decision | concept 열 | 하는 일 |
| --- | --- | --- |
| `LINK`    | 개념 id | 그 개념의 표현으로 넣는다 (`kind=synonym`) |
| `NEW`     | `이름/분류` 예: `balletcore/style` | 개념을 만들고 이 표기를 표현으로 넣는다 |
| `EXCLUDE` | 비움 | `generic` 분류의 `countable=false` 개념으로 넣는다. 매일 다시 올라오지 않는다 |
| `DEFER`   | 비움 | 이번엔 넘어간다. 상태만 `QUEUED` 로 두어 다음 export 에서 뒤로 간다 |
| 비움      | — | 아무것도 하지 않는다 |

결정마다 `pl_mapping_decision` 에 한 줄 남고, 하나라도 반영되면 사전 버전이 1 오른다. 반영된
표현은 다음 `concept` Job 실행이 창 안의 기사에 저절로 붙인다.

## 자동 반영 되돌리기

자동 판정이 바꾼 것은 전부 원장(`pl_concept_change`)에 회차 번호로 남는다. 회차 하나를 통째로
내리거나 표기 하나만 내릴 수 있다.

```sh
.venv/Scripts/python scripts/concept-review.py runs --profile dev
.venv/Scripts/python scripts/concept-review.py rollback --run auto-20260923T003612Z \
    --by human:jk --dry-run
.venv/Scripts/python scripts/concept-review.py rollback --expr ko 무신사 --by human:jk
```

지우지 않고 상태를 내린다 — 표현은 `REJECTED`, 새 개념은 `RETIRED`, 기사에 붙은 행은 치운다.
되돌린 표기에는 사람 보류(`DEFER`)가 최신 결정으로 남아 순위 제외가 풀리고, 자동 판정이 다시
손대지 않는다. 검수 대기(`PENDING`)로 돌아가므로 다음 `export` 에 나온다.

**사람이 손댄 것은 되돌리지 않는다.** 원장에는 자동 판정이 한 일만 적힌다. 새 개념이라도 검수가
세는 개념으로 올렸거나 표현을 더 붙였으면 그 개념은 그대로 둔다.

사람이 `apply` 로 넣은 것을 잘못 넣었으면 아직 SQL 이다 — `concept_expression.status` 를
`REJECTED` 로 바꾸고 결정을 남긴다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

# 저장소의 `src` 를 경로에 올린다. 스크립트가 패키지 밖에 있어서다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.normalize import concept_key  # noqa: E402
from trendin.spark.io import jdbc  # noqa: E402
from trendin.spark.io.concepts import (  # noqa: E402
    CONCEPT,
    EXPRESSION,
    UNMAPPED,
    UNMAPPED_CONTEXT,
    ConceptSink,
)

COLUMNS = (
    "lang", "normalized", "surface", "articles", "contexts",
    "decision", "concept", "note", "why",
)
DECISIONS = ("LINK", "NEW", "EXCLUDE", "DEFER")

# 관찰 모드의 판정을 `decision`·`concept` 열에 미리 적는다. 검수자가 하는 일이 "수백 개를
# 판단한다" 에서 "틀린 줄만 고친다" 로 바뀐다. `apply` 는 이 열을 그대로 읽으므로 **손대지
# 않은 줄은 제안대로 반영된다** — 훑고 나서 넣으라는 뜻이다.
#
# `DEFER` 와 모양이 어긋난 제안은 비워 둔다. 판정이 스스로 못 고르겠다고 한 자리라 사람이
# 채워야 한다. `why` 는 왜 그렇게 봤는지이고 `apply` 가 읽지 않는다.

EXPORT_SQL = f"""
SELECT u.lang, u.normalized, u.surface_sample, u.article_count, u.proposal,
       coalesce((SELECT string_agg(c.snippet, ' ⏎ ' ORDER BY c.article_id)
                   FROM (SELECT snippet, article_id FROM {UNMAPPED_CONTEXT}
                          WHERE unmapped_id = u.id ORDER BY article_id LIMIT 3) c), '')
  FROM {UNMAPPED} u
 WHERE u.status IN ('PENDING', 'QUEUED')
   AND u.article_count >= %s
 ORDER BY (u.status = 'QUEUED'), u.article_count DESC, u.lang, u.normalized
"""


def export(args: argparse.Namespace) -> int:
    config = load_config(args.profile)
    min_articles = int(config.get("concept.unmapped.min_articles", 1))
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(EXPORT_SQL, (min_articles,))
        rows = cur.fetchall()
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    writer.writerow(COLUMNS)
    prefilled = 0
    for lang, normalized, surface, articles, proposal, contexts in rows:
        decision, concept, why = _suggestion(proposal)
        if decision:
            prefilled += 1
        writer.writerow(
            [lang, normalized, surface, articles, contexts, decision, concept, "", why]
        )
    print(f"{len(rows)}건 · 제안이 채워진 줄 {prefilled}건", file=sys.stderr)
    return 0


def _suggestion(proposal) -> tuple[str, str, str]:
    """`pl_concept_unmapped.proposal` 을 검수 열 셋(`decision`·`concept`·`why`)으로 옮긴다.

    제안이 없거나 모양이 어긋나면 앞의 둘을 비운다 — 채우면 사람이 안 보고 넘긴다.
    """
    if not isinstance(proposal, dict):
        return ("", "", "")
    decision = str(proposal.get("decision") or "")
    name = str(proposal.get("english_name") or "").strip()
    category = str(proposal.get("category") or "").strip()
    why = " · ".join(
        part
        for part in (
            f"{name}/{category}" if name and category else name or category,
            str(proposal.get("reason") or ""),
            str(proposal.get("outcome") or ""),
        )
        if part
    )
    if decision == "LINK" and proposal.get("concept_id") is not None:
        return ("LINK", str(proposal["concept_id"]), why)
    if decision == "NEW_CONCEPT" and name and category:
        return ("NEW", f"{name}/{category}", why)
    if decision == "EXCLUDE":
        return ("EXCLUDE", "", why)
    return ("", "", why)


def apply(args: argparse.Namespace) -> int:
    config = load_config(args.profile)
    sink = ConceptSink(config)
    version_before = sink.current_version()
    applied = 0
    with open(args.file, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        decisions = [row for row in reader if (row.get("decision") or "").strip()]

    if not decisions:
        print("결정이 적힌 행이 없다", file=sys.stderr)
        return 0

    with jdbc.connection(config) as conn, conn.cursor() as cur:
        for row in decisions:
            decision = row["decision"].strip().upper()
            if decision not in DECISIONS:
                raise SystemExit(f"모르는 결정: {decision!r} ({row['lang']} {row['normalized']})")
            lang, normalized, surface = (
                row["lang"].strip(),
                row["normalized"].strip(),
                row["surface"].strip(),
            )
            note = (row.get("note") or "").strip()
            concept_id: int | None = None

            if decision == "LINK":
                concept_id = int(row["concept"])
                _insert_expression(cur, concept_id, lang, surface, normalized, "synonym", args.by)
            elif decision == "NEW":
                name, _, category = (row.get("concept") or "").partition("/")
                if not name or not category:
                    raise SystemExit(f"NEW 는 concept 열에 '이름/분류' 가 필요하다: {normalized}")
                concept_id = _insert_concept(
                    cur, name.strip(), category.strip(), True, note, args.by
                )
                # 대표 이름(영어)도 표현으로 넣는다. 그래야 다음 영어 기사가 바로 붙는다.
                _insert_expression(
                    cur, concept_id, "en", name.strip(), concept_key(name), "canonical", args.by
                )
                _insert_expression(cur, concept_id, lang, surface, normalized, "synonym", args.by)
            elif decision == "EXCLUDE":
                # 일반 단어. 영어 이름이 없으니 표기 자체를 대표로 둔다 — 화면에 안 나가는 개념이다.
                concept_id = _insert_concept(
                    cur, surface, "generic", False, note or "검수에서 제외", args.by
                )
                _insert_expression(cur, concept_id, lang, surface, normalized, "canonical", args.by)

            status = "QUEUED" if decision == "DEFER" else "RESOLVED"
            cur.execute(
                f"UPDATE {UNMAPPED} SET status = %s WHERE lang = %s AND normalized = %s",
                (status, lang, normalized),
            )
            decision_name = {
                "LINK": "LINK",
                "NEW": "NEW_CONCEPT",
                "EXCLUDE": "EXCLUDE",
                "DEFER": "DEFER",
            }[decision]
            cur.execute(
                "INSERT INTO pl_mapping_decision "
                "(lang, normalized, decision, concept_id, decided_by, evidence, "
                "dictionary_version) "
                "VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)",
                (
                    lang,
                    normalized,
                    decision_name,
                    concept_id,
                    args.by,
                    json.dumps({"note": note, "surface": surface}, ensure_ascii=False),
                    version_before + 1,
                ),
            )
            applied += 1

    changed = [d for d in decisions if d["decision"].strip().upper() != "DEFER"]
    if changed:
        version = sink.bump_version(
            note=f"검수 반영 {len(changed)}건 ({Path(args.file).name})", changed_by=args.by
        )
        print(f"{applied}건 반영 · 사전 버전 {version}", file=sys.stderr)
    else:
        print(f"{applied}건 반영 (전부 DEFER — 버전 그대로)", file=sys.stderr)
    return 0


def _insert_concept(
    cur, name: str, category: str, countable: bool, description: str, by: str
) -> int:
    cur.execute(
        f"""
        INSERT INTO {CONCEPT} (canonical_name, description, category, countable, source)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (canonical_name, category) DO UPDATE SET updated_at = now()
        RETURNING id
        """,
        (name, description or None, category, countable, f"review:{by}"),
    )
    return int(cur.fetchone()[0])


def _insert_expression(
    cur, concept_id: int, lang: str, surface: str, normalized: str, kind: str, by: str
) -> None:
    cur.execute(
        f"""
        INSERT INTO {EXPRESSION} (concept_id, lang, surface, normalized, kind, source, decided_by)
        VALUES (%s, %s, %s, %s, %s, 'review', %s)
        ON CONFLICT (lang, normalized, concept_id) DO UPDATE
           SET status = 'ACTIVE', decided_by = EXCLUDED.decided_by
        """,
        (concept_id, lang, surface, normalized, kind, by),
    )


def runs(args: argparse.Namespace) -> int:
    """최근 자동 반영 회차. 되돌릴 회차 번호를 여기서 고른다."""
    sink = ConceptSink(load_config(args.profile))
    rows = sink.auto_runs(limit=args.limit)
    print("run_id\t시각(UTC)\t연결\t새개념\t제외\t전체\t되돌림")
    for run_id, started, links, mints, excludes, total, reverted in rows:
        cells = (run_id, f"{started:%Y-%m-%d %H:%M}", links, mints, excludes, total, reverted)
        print("\t".join(str(cell) for cell in cells))
    print(f"{len(rows)}회차", file=sys.stderr)
    return 0


def rollback(args: argparse.Namespace) -> int:
    """자동 반영을 회차 단위 또는 표기 단위로 되돌린다. `--dry-run` 이면 고르기만 한다."""
    from trendin.spark.concept import rollback as planner

    if bool(args.run) == bool(args.expr):
        raise SystemExit("--run 과 --expr 중 하나만 준다")
    key = (args.expr[0], args.expr[1]) if args.expr else None
    sink = ConceptSink(load_config(args.profile))
    changes = sink.changes(run_id=args.run, key=key)
    plan = planner.plan(changes, run_id=args.run, key=key)
    target = args.run or f"{key[0]} {key[1]}"
    if plan.empty:
        print(
            f"{target}: 되돌릴 자동 변경이 없다 (이미 되돌렸거나 사람이 한 일이다)",
            file=sys.stderr,
        )
        return 0
    by_action: dict[str, int] = {}
    for change in changes:
        if change.id in plan.change_ids:
            by_action[change.action] = by_action.get(change.action, 0) + 1
    print(
        f"{target}: 원장 {len(plan.change_ids)}줄 {by_action} · 표현 {len(plan.expressions)} · "
        f"개념 {len(plan.concepts)} · 표기 {len(plan.keys)}",
        file=sys.stderr,
    )
    for lang, normalized in plan.keys[:30]:
        print(f"  {lang}\t{normalized}", file=sys.stderr)
    if args.dry_run:
        print("dry-run — 쓰지 않는다", file=sys.stderr)
        return 0
    result = sink.revert(plan, by=args.by, note=f"자동 반영 되돌리기 {target}")
    print(
        f"되돌렸다: 표현 {result['expressions']} REJECTED · 개념 {result['concepts']} RETIRED · "
        f"기사 연결 {result['article_rows']}행 삭제 · 표기 {result['keys']}개 검수 대기 · "
        f"사전 버전 {result['version']}",
        file=sys.stderr,
    )
    if result["kept_concepts"]:
        print(
            f"사람이 손댄 개념은 두었다: {result['kept_concepts']}", file=sys.stderr
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export", help="검수할 미등록 표현을 TSV 로 표준출력에")
    e.add_argument("--profile", default=None)
    e.set_defaults(func=export)
    a = sub.add_parser("apply", help="결정 열이 채워진 TSV 를 반영")
    a.add_argument("file")
    a.add_argument("--profile", default=None)
    a.add_argument("--by", required=True, help="결정한 사람. 예: human:jk")
    a.set_defaults(func=apply)
    r = sub.add_parser("runs", help="최근 자동 반영 회차를 본다")
    r.add_argument("--profile", default=None)
    r.add_argument("--limit", type=int, default=20)
    r.set_defaults(func=runs)
    b = sub.add_parser("rollback", help="자동 반영을 회차 또는 표기 단위로 되돌린다")
    b.add_argument("--run", help="되돌릴 회차. `runs` 의 run_id")
    b.add_argument("--expr", nargs=2, metavar=("LANG", "NORMALIZED"), help="되돌릴 표기 하나")
    b.add_argument("--profile", default=None)
    b.add_argument("--by", required=True, help="되돌린 사람. 예: human:jk")
    b.add_argument("--dry-run", action="store_true", help="무엇을 내릴지 보여 주기만 한다")
    b.set_defaults(func=rollback)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
