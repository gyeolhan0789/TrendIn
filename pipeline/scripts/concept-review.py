#!/usr/bin/env python
"""미등록 표현 검수 — TSV 한 장으로 내보내고, 결정을 적어 되돌려 넣는다.

```sh
.venv/Scripts/python scripts/concept-review.py export --profile local > review.tsv
#   ... review.tsv 의 decision 열을 채운다 ...
.venv/Scripts/python scripts/concept-review.py apply  --profile local review.tsv --by human:jk
```

MVP 에서 관리 화면 대신 쓰는 것이다. 하루 검수량이 수십 건이면 이걸로 충분하고, 사람이 파일로
못 따라갈 때 화면을 만든다 (2026-09-17 설계 §2).

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

## 되돌리기

잘못 붙였으면 `concept_expression.status` 를 `REJECTED` 로 바꾸고 `UNLINK` 결정을 남긴다. 이
스크립트에는 아직 그 명령이 없다 — 첫 주는 SQL 로 하고, 필요가 확인되면 명령으로 올린다.
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

COLUMNS = ("lang", "normalized", "surface", "articles", "contexts", "decision", "concept", "note")
DECISIONS = ("LINK", "NEW", "EXCLUDE", "DEFER")

EXPORT_SQL = f"""
SELECT u.lang, u.normalized, u.surface_sample, u.article_count,
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
    for lang, normalized, surface, articles, contexts in rows:
        writer.writerow([lang, normalized, surface, articles, contexts, "", "", ""])
    print(f"{len(rows)}건", file=sys.stderr)
    return 0


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
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
