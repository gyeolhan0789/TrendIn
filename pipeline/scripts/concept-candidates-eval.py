#!/usr/bin/env python
"""후보 생성기가 미등록 표기에서 몇 건을 건지나 — 크레딧 없이 재는 자.

```sh
# 저장소의 초기 사전만으로, 표기를 인자로 준다 (DB 없이 돈다)
.venv/Scripts/python scripts/concept-candidates-eval.py --words 샤넬 디올 버버리

# 실 DB 의 미등록 표 전체 (터널 열고, concept-run.py 와 같은 환경변수)
.venv/Scripts/python scripts/concept-candidates-eval.py --dictionary db --profile local --detail
```

**LLM 을 부르지 않는다.** 이 스크립트가 답하는 것은 하나다 — 미등록 더미에서 후보가 **생기는**
비율이 얼마이고, 그중 어느 규칙이 얼마를 기여하나. 정답이 후보 안에 없으면 LLM 을 아무리 잘
써도 못 붙이므로, 프롬프트를 손대기 전에 이 숫자를 먼저 본다.

세는 것은 "후보가 생긴 건수" 이지 "맞는 후보가 생긴 건수" 가 아니다. 맞는지는 사람이 `--detail`
출력을 읽어야 안다 — 그 판단을 자동화하는 것이 다음 단계의 LLM 판정이다.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trendin.spark.common.config import load_config  # noqa: E402
from trendin.spark.concept.candidates import (  # noqa: E402
    DEFAULT_LIMIT,
    DEFAULT_MIN_SIMILARITY,
    CandidateIndex,
)
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression  # noqa: E402
from trendin.spark.concept.normalize import concept_key, lang_of_surface  # noqa: E402
from trendin.spark.concept.seed import load_seed_dir  # noqa: E402
from trendin.spark.io import jdbc  # noqa: E402
from trendin.spark.io.concepts import UNMAPPED, ConceptSink  # noqa: E402

UNMAPPED_SQL = f"""
SELECT lang, normalized, surface_sample, article_count
  FROM {UNMAPPED}
 WHERE status IN ('PENDING', 'QUEUED')
 ORDER BY article_count DESC, lang, normalized
"""


def seed_dictionary(seed_dir: Path) -> Dictionary:
    """저장소의 `conf/concepts/*.json` → 메모리 사전. 번호는 읽은 순서로 매긴다.

    DB 의 번호와 다르다. 후보가 **생기는지** 를 보는 용도라 상관없고, 대신 터널 없이 돈다.
    """
    concepts: list[Concept] = []
    expressions: list[Expression] = []
    for index, seed in enumerate(load_seed_dir(seed_dir), start=1):
        concepts.append(
            Concept(
                concept_id=index,
                canonical_name=seed.canonical_name,
                category=seed.category,
                countable=seed.countable,
            )
        )
        for expression in seed.expressions:
            expressions.append(
                Expression(
                    expression_id=len(expressions) + 1,
                    concept_id=index,
                    lang=expression.lang,
                    normalized=expression.normalized,
                )
            )
    return Dictionary(concepts, expressions)


def unmapped_from_db(config) -> list[tuple[str, str, str, int]]:
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(UNMAPPED_SQL)
        return [(lang, key, surface, count) for lang, key, surface, count in cur.fetchall()]


def unmapped_from_words(words: list[str]) -> list[tuple[str, str, str, int]]:
    rows = []
    for word in words:
        key = concept_key(word)
        if key:
            rows.append((lang_of_surface(word, None), key, word, 1))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dictionary", choices=("seed", "db"), default="seed")
    parser.add_argument("--profile", default="local")
    parser.add_argument("--words", nargs="*", default=None, help="미등록 대신 직접 준 표기들")
    parser.add_argument("--min-articles", type=int, default=1)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--min-similarity", type=float, default=DEFAULT_MIN_SIMILARITY)
    parser.add_argument("--detail", action="store_true", help="표기별 후보를 TSV 로 찍는다")
    args = parser.parse_args(argv)

    config = None
    if args.dictionary == "db" or args.words is None:
        config = load_config(args.profile)

    if args.dictionary == "db":
        dictionary = ConceptSink(config).load_dictionary()
    else:
        dictionary = seed_dictionary(ROOT / "spark" / "conf" / "concepts")
    index = CandidateIndex(dictionary)
    print(
        f"사전 개념 {len(dictionary.concepts()):,} · 표현 {len(index):,}",
        file=sys.stderr,
    )

    if args.words is not None:
        rows = unmapped_from_words(args.words)
    else:
        rows = [r for r in unmapped_from_db(config) if r[3] >= args.min_articles]
    print(f"미등록 {len(rows):,} 건", file=sys.stderr)

    by_source: Counter[str] = Counter()
    with_candidate = 0
    articles_total = sum(row[3] for row in rows)
    articles_covered = 0
    if args.detail:
        print("lang\tnormalized\tsurface\tarticles\tsource\tscore\tconcept\tcategory")

    for lang, key, surface, count in rows:
        found = index.generate(lang, key, limit=args.limit, min_similarity=args.min_similarity)
        if not found:
            continue
        with_candidate += 1
        articles_covered += count
        by_source[found[0].source] += 1
        if args.detail:
            for candidate in found:
                concept = dictionary.concept(candidate.concept_id)
                print(
                    f"{lang}\t{key}\t{surface}\t{count}\t{candidate.source}\t"
                    f"{candidate.score}\t{concept.canonical_name}\t{concept.category}"
                )

    total = len(rows) or 1
    print(
        f"\n후보가 생긴 표기 {with_candidate}/{len(rows)} ({with_candidate / total:.1%})",
        file=sys.stderr,
    )
    if articles_total:
        print(
            f"그 표기들의 기사 발생 {articles_covered}/{articles_total} "
            f"({articles_covered / articles_total:.1%})",
            file=sys.stderr,
        )
    print("가장 높은 등급을 준 규칙별 건수:", file=sys.stderr)
    for source, n in by_source.most_common():
        print(f"  {source:12} {n:5}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
