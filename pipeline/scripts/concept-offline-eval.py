#!/usr/bin/env python
"""개념 사전을 DB 없이 실데이터 표본에 대 본다 — 초기 사전이 실제 기사 키워드를 몇 퍼센트 덮나.

```sh
.venv/Scripts/python scripts/concept-offline-eval.py                 # 스냅숏 30건
.venv/Scripts/python scripts/concept-offline-eval.py --top 40        # 미등록 상위 40개까지
```

입력은 `spark/tests/fixtures/snapshots.json` 이다 — 실제 수집 기사 30건의 추출 결과에서 문서당
상위 후보 15개. **승격을 거친 키워드가 아니라 문서당 상위 후보**라 실제 운영 입력보다 잡음이
많고(`가을` · `정리` 같은 것이 섞인다), 그래서 여기 나오는 커버리지는 **하한**이다. 진짜 숫자는
DB 에서 `concept --dry-run` 이 낸다. 이 스크립트는 그 전에 초기 사전의 구멍이 어디인지 보는 용도다.

사전은 `spark/conf/concepts/*.json` 을 파싱해 메모리에 만든다. DB 가 발행할 id 대신 순번을 쓴다.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trendin.spark.concept.dictionary import Concept, Dictionary, Expression  # noqa: E402
from trendin.spark.concept.mapping import Keyword, map_article  # noqa: E402
from trendin.spark.concept.normalize import concept_key, lang_of_surface  # noqa: E402
from trendin.spark.concept.seed import load_seed_dir  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "spark" / "conf" / "concepts"
SNAPSHOTS = ROOT / "spark" / "tests" / "fixtures" / "snapshots.json"


def build_dictionary(seed_dir: Path) -> tuple[Dictionary, dict[int, str]]:
    concepts, expressions, names = [], [], {}
    parents: dict[str, int] = {}
    seeds = load_seed_dir(seed_dir)
    for cid, seed in enumerate(seeds, start=1):
        parents[(seed.canonical_name.lower(), seed.category)] = cid
    eid = 0
    for cid, seed in enumerate(seeds, start=1):
        parent = None
        if seed.parent_name:
            parent = parents.get((seed.parent_name.lower(), seed.category))
        concepts.append(Concept(cid, seed.canonical_name, seed.category, parent, seed.countable))
        names[cid] = f"{seed.canonical_name} [{seed.category}]"
        for e in seed.expressions:
            eid += 1
            expressions.append(Expression(eid, cid, e.lang, e.normalized))
    # 같은 (lang, normalized) 가 개념 둘에 걸리면 모호 — 사전이 스스로 표시한다.
    seen: dict[tuple[str, str], set[int]] = collections.defaultdict(set)
    for e in expressions:
        seen[(e.lang, e.normalized)].add(e.concept_id)
    expressions = [
        Expression(e.expression_id, e.concept_id, e.lang, e.normalized,
                   ambiguous=len(seen[(e.lang, e.normalized)]) > 1)
        for e in expressions
    ]
    return Dictionary(concepts, expressions), names


def read_from_db(profile: str, domain: str, days: int) -> dict[str, dict]:
    """승격된 키워드의 기사별 표기를 DB 에서 읽어 스냅숏과 같은 모양으로 돌려준다.

    `SELECT` 하나뿐이다 — 표를 만들지도 쓰지도 않는다. `concept` Job 이 실제로 읽는 질의
    (`io/concepts.OCCURRENCES_SQL`)를 그대로 쓰므로, 여기서 나온 숫자가 운영 입력 기준이다.
    """
    from trendin.spark.common.config import load_config
    from trendin.spark.io import jdbc
    from trendin.spark.io.concepts import OCCURRENCES_SQL

    config = load_config(profile)
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(OCCURRENCES_SQL, (domain, days))  # pl_ 표는 슬러그(fashion)로 저장한다
        for content_id, surface, _title in cur.fetchall():
            grouped[str(content_id)].append(str(surface))
    # 스냅숏의 "key | surface | ..." 줄 모양을 흉내 낸다. 두 번째 칸만 읽으므로 나머지는 비운다.
    return {
        doc_id: {"extract": {"top": [f" | {surface} | " for surface in surfaces]}}
        for doc_id, surfaces in grouped.items()
    }


def read_from_articles(
    path: Path | None, min_docs: int, articles: list[dict] | None = None
) -> dict[str, dict]:
    """방금 받은 기사(`probe --json` 의 JSON Lines)를 실제 정제·추출 경로에 태워 후보를 만든다.

    DB 없이 **승격 후 입력에 가장 가까운 것**이다. 문서당 상위 15개가 아니라 후보 전부를 쓰고,
    서로 다른 기사 `min_docs` 건 이상에 나온 비교키만 남긴다 — 승격 관문(기사 5 · 저자 3)의
    문서 수 축을 흉내 낸 것이다. 기사가 100건 안팎이면 3 이 적당하다.

    추출은 `spark/scripts/update-snapshots.py` 의 경로를 그대로 쓴다 (스냅숏 테스트와 같은 함수).
    """
    import importlib.util

    script = ROOT / "spark" / "scripts" / "update-snapshots.py"
    spec = importlib.util.spec_from_file_location("update_snapshots", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    from trendin.spark.common.config import load_config

    config = load_config("local")
    if articles is None:
        assert path is not None
        lines = path.read_text(encoding="utf-8").splitlines()
        articles = [json.loads(line) for line in lines if line.strip()]

    per_doc: dict[str, list] = {}
    df: collections.Counter = collections.Counter()
    for article in articles:
        doc_id = f"{article.get('source')}-{article.get('article_id')}"
        document = module.build_document(article, {}, ingest_run_id="live-eval")
        domain = str(article.get("domain") or "fashion")
        extraction = module.extract_document(
            document.title, document.body, document.lang, options=module.options_for(config, domain)
        )
        per_doc[doc_id] = list(extraction.candidates)
        for key in {c.key for c in extraction.candidates}:
            df[key] += 1

    kept_keys = {key for key, n in df.items() if n >= min_docs}
    out: dict[str, dict] = {}
    for doc_id, candidates in per_doc.items():
        surfaces = sorted({c.surface for c in candidates if c.key in kept_keys})
        out[doc_id] = {"extract": {"top": [f" | {s} | " for s in surfaces]}}
    print(f"기사 {len(articles)}건 · 비교키 {len(df)}개 중 {min_docs}건 이상: {len(kept_keys)}개")
    return out


def article_from_text(path: Path) -> dict:
    """글 한 편(`.txt`) → 기사 모양. 첫 줄이 제목, 나머지가 본문이다.

    사람이 아무 기사나 긁어 붙여 보는 용도라, 정제 경로가 요구하는 칸은 그럴듯한 값으로 채운다.
    `route` 를 `rss` 로 두면 매체 규칙(제목·본문·요약)으로 정제된다.
    """
    from datetime import datetime, timezone

    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((line.strip() for line in lines if line.strip()), path.stem)
    body = "\n".join(lines[1:]).strip()
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "domain": "fashion",
        "source": "manual",
        "route": "rss",
        "article_id": path.stem,
        "url": f"https://manual.local/{path.stem}",
        "title": title,
        "body_text": body,
        "summary": None,
        "published_at": now,
        "collected_at": now,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed-dir", type=Path, default=SEED_DIR)
    parser.add_argument("--snapshots", type=Path, default=SNAPSHOTS)
    parser.add_argument("--top", type=int, default=25, help="미등록 상위 몇 개를 보여 주나")
    parser.add_argument(
        "--from-db",
        metavar="PROFILE",
        default=None,
        help="스냅숏 대신 DB 의 승격 키워드를 읽는다 (SELECT 만, 아무것도 쓰지 않는다). "
        "예: --from-db local. 접속은 APP_DB_URL · APP_DB_USER · APP_DB_PASSWORD 환경변수",
    )
    parser.add_argument("--domain", default="fashion", help="--from-db 일 때 도메인 슬러그")
    parser.add_argument("--days", type=int, default=30, help="--from-db 일 때 최근 며칠")
    parser.add_argument(
        "--articles",
        type=Path,
        default=None,
        help="`probe --json` 으로 받은 기사 JSON Lines. 실제 추출 경로에 태운다 (DB 없음)",
    )
    parser.add_argument(
        "--min-docs",
        type=int,
        default=None,
        help="--articles 일 때 몇 기사 이상에 나온 후보만 남기나 (기본 3, --text 는 1)",
    )
    parser.add_argument(
        "--text",
        type=Path,
        nargs="+",
        default=None,
        help="글 파일(.txt) 하나 이상. 첫 줄이 제목, 나머지가 본문. 긁어 온 기사를 그대로 붙인다",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="기사마다 무엇이 어디에 붙었는지 다 찍는다"
    )
    args = parser.parse_args()

    dictionary, names = build_dictionary(args.seed_dir)
    if args.text:
        articles = [article_from_text(p) for p in args.text]
        snapshots = read_from_articles(None, args.min_docs or 1, articles=articles)
        print()
    elif args.articles:
        snapshots = read_from_articles(args.articles, args.min_docs or 3)
        print()
    elif args.from_db:
        snapshots = read_from_db(args.from_db, args.domain, args.days)
        print(f"DB 에서 읽음 (읽기만): 최근 {args.days}일 · {args.domain}")
        print(f"기사 {len(snapshots)}건")
        print()
    else:
        snapshots = json.loads(args.snapshots.read_text(encoding="utf-8"))

    total_kw = mapped_kw = 0
    method = collections.Counter()
    concept_hits = collections.Counter()
    unmapped = collections.Counter()
    unmapped_docs = collections.defaultdict(set)
    deferred = collections.Counter()
    docs_with_concept = 0

    for doc_id, snap in snapshots.items():
        surfaces = []
        for line in snap.get("extract", {}).get("top", []):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                surfaces.append(parts[1])  # 두 번째 칸이 원표기
        total_kw += len(surfaces)
        result = map_article(0, "ko", [Keyword(s) for s in surfaces], dictionary)
        if result.rows:
            docs_with_concept += 1
        if args.verbose or len(snapshots) <= 3:
            print(f"── {doc_id}  (표기 {len(surfaces)}개)")
            for row in result.rows:
                shown = [
                    s for s in surfaces
                    if any(h.concept.concept_id == row.concept_id
                           for h in dictionary.lookup(lang_of_surface(s, "ko"), concept_key(s)))
                ]
                label = names[row.concept_id]
                print(f"  붙음  {label:40s} ← {', '.join(shown[:6])}  [{row.method}]")
            for u in result.unmapped:
                print(f"  미등록  {u.surface}")
            for d in result.deferred:
                print(f"  유보    {d.normalized} → {[names[c] for c in d.concept_ids]}")
            print()
        for row in result.rows:
            mapped_kw += len(row.expression_ids)
            method[row.method] += 1
            concept_hits[names[row.concept_id]] += 1
        for u in result.unmapped:
            unmapped[(u.lang, u.surface)] += 1
            unmapped_docs[(u.lang, u.surface)].add(doc_id)
        for d in result.deferred:
            deferred[d.normalized] += 1

    docs = len(snapshots)
    print(f"사전: 개념 {len(dictionary.concepts())} · 표현 {len(dictionary)}")
    print(f"문서 {docs} · 후보 표기 {total_kw} (문서당 상위 후보, 승격 전)")
    print()
    rate = mapped_kw / max(total_kw, 1) * 100
    print(f"개념에 붙은 표기   {mapped_kw:4d} / {total_kw}  ({rate:.1f}%)")
    print(f"개념이 하나라도 붙은 문서  {docs_with_concept} / {docs}")
    print(f"붙인 방법  {dict(method)}")
    print(f"유보  {sum(deferred.values())}건  {dict(deferred.most_common(5))}")
    print()
    print("가장 많이 붙은 개념:")
    for name, n in concept_hits.most_common(12):
        print(f"  {n:3d}  {name}")
    print()
    occurrences = sum(unmapped.values())
    print(f"미등록 표기 상위 {args.top} (고유 {len(unmapped)}개 · 발생 {occurrences}건):")
    for (lang, surface), n in unmapped.most_common(args.top):
        print(f"  {n:3d}  문서 {len(unmapped_docs[(lang, surface)]):2d}  {lang}  {surface}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
