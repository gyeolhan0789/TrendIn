"""초기 사전 — `spark/conf/concepts/*.json` 을 읽어 `concept` · `concept_expression` 에 넣는다.

## 파일 모양

```json
{
  "source": "wikidata",          // 또는 "seed" (손으로 만든 것). SOURCE_LICENSES 의 키
  "license": "CC0-1.0",          // 없으면 source 의 기본값. SPDX 이름으로 적는다
  "category": "brand",           // concept_category.code
  "items": [
    {
      "id": "Q894874",           // 출처 쪽 식별자. wikidata 면 필수
      "labels":  {"en": "Bottega Veneta", "ko": "보테가 베네타", "ja": "ボッテガ・ヴェネタ"},
      "aliases": {"ko": ["보테가베네타"], "ja": ["BOTTEGA VENETA"]},
      "display_ko": "보테가 베네타",   // 없으면 labels.ko
      "description": "…",
      "parent": "boots",         // 같은 파일 안 다른 항목의 labels.en — 상위 개념
      "countable": true          // false 면 일반 단어 (기억하되 세지 않는다)
    }
  ]
}
```

`labels.en` 이 대표 이름이다. 없는 항목은 거부한다 — 개념 표의 이름 규약이 영어라서다.

## 출처를 행마다 남긴다

표현에는 종류(`source`) · 식별자(`source_id`) · 이용 조건(`license`) 이 함께 들어간다.
나눠 두는 이유는 **출처 단위로 내리기 위해서다** — 대량으로 부은 사전이 매핑을 깎으면
(`scripts/concept-dump-diff.py` 가 그것을 잡는다) 그 출처의 행만 골라 `REJECTED` 로
내려야 하는데, 종류만 있으면 위키데이터 브랜드 1.4만 건과 이번에 부은 것이 한 값이 된다.
이용 조건을 같이 적는 것은 나중에 무엇을 배포할 수 있는지 되짚기 위한 것이다.

## 사람이 고친 것을 덮지 않는다

초기 사전은 **다시 넣어도 안전해야** 한다 (위키데이터는 한 달에 한 번쯤 갱신한다). 그래서
개념 upsert 는 비어 있는 칸만 채우고(`coalesce`), 표현은 이미 있으면 건드리지 않는다 —
검수자가 `REJECTED` 로 내린 표현이 다음 초기 사전 적재에 되살아나면 안 된다.

**pyspark 를 import 하지 않는다** (층 1). `apply_seed` 만 DB 를 친다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field, replace
from pathlib import Path

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.normalize import concept_key
from trendin.spark.io import jdbc
from trendin.spark.io.concepts import CONCEPT, EXPRESSION

log = get_logger(__name__)

KIND_CANONICAL = "canonical"
KIND_SYNONYM = "synonym"
KIND_VARIANT = "variant"

# 출처 종류와 그 기본 이용 조건. 파일이 `license` 를 적으면 그것이 이긴다.
#
# **여기 없는 출처는 받지 않는다.** 이용 조건을 모르는 데이터가 사전에 섞이면 나중에 무엇을
# 배포할 수 있는지 되짚을 수 없다. 새 출처를 들일 때 이 표에 한 줄 더하는 것이 그 확인이다.
# 위키데이터의 구조화 데이터는 CC0 라 출처 표시 의무도 없다 (`scripts/seed-concepts-wikidata.py`).
SOURCE_LICENSES: Mapping[str, str | None] = {
    "wikidata": "CC0-1.0",
    "seed": None,  # 우리가 손으로 만든 것 — 조건이 없다
}

CATEGORIES = frozenset(
    {
        "apparel",
        "footwear",
        "accessory",
        "material",
        "color",
        "style",
        "brand",
        "designer",
        "person",
        "media",
        "event",
        "generic",
    }
)


@dataclass(frozen=True, slots=True)
class SeedExpression:
    lang: str
    surface: str
    normalized: str
    kind: str


@dataclass(frozen=True, slots=True)
class SeedConcept:
    canonical_name: str
    category: str
    source: str  # "wikidata:Q894874" · "seed:vocabulary-core.json"
    display_ko: str | None = None
    description: str | None = None
    countable: bool = True
    parent_name: str | None = None
    license: str | None = None
    expressions: tuple[SeedExpression, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SeedResult:
    concepts_seen: int
    concepts_new: int
    expressions_new: int
    parents_set: int


def parse_seed(document: Mapping, *, file_name: str) -> tuple[SeedConcept, ...]:
    """파일 하나 → 개념 목록. 모양이 틀리면 `ValueError` — 조용히 건너뛰지 않는다."""
    source = str(document.get("source") or "")
    category = str(document.get("category") or "")
    if source not in SOURCE_LICENSES:
        allowed = " 또는 ".join(sorted(SOURCE_LICENSES))
        raise ValueError(f"{file_name}: source 는 {allowed} 여야 한다: {source!r}")
    license_ = _clean(document.get("license")) or SOURCE_LICENSES[source]
    if category not in CATEGORIES:
        raise ValueError(f"{file_name}: 모르는 category: {category!r}")
    items = document.get("items")
    if not isinstance(items, list):
        raise ValueError(f"{file_name}: items 가 목록이어야 한다")

    concepts: list[SeedConcept] = []
    seen_names: set[str] = set()
    for index, item in enumerate(items):
        labels = item.get("labels") or {}
        english = labels.get("en")
        if not english or not str(english).strip():
            raise ValueError(f"{file_name} 항목 {index}: labels.en 이 없다 — 대표 이름은 영어다")
        canonical = str(english).strip()
        if canonical.lower() in seen_names:
            # 같은 파일 안 중복은 출처 데이터의 잡음이다 (위키데이터의 사람·회사 쌍). 먼저 온 것만.
            log.warning("%s 항목 %d: 대표 이름 중복 — 건너뛴다: %s", file_name, index, canonical)
            continue
        seen_names.add(canonical.lower())

        if source == "wikidata":
            if not item.get("id"):
                raise ValueError(f"{file_name} 항목 {index}: wikidata 항목은 id 가 필요하다")
            concept_source = f"wikidata:{item['id']}"
        else:
            concept_source = f"seed:{file_name}"

        expressions = _expressions(labels, item.get("aliases") or {})
        concepts.append(
            SeedConcept(
                canonical_name=canonical,
                category=category,
                source=concept_source,
                display_ko=_clean(item.get("display_ko")) or _clean(labels.get("ko")),
                description=_clean(item.get("description")),
                countable=bool(item.get("countable", True)),
                parent_name=_clean(item.get("parent")),
                license=license_,
                expressions=expressions,
            )
        )
    return tuple(concepts)


def load_seed_dir(path: Path) -> tuple[SeedConcept, ...]:
    """디렉터리의 `*.json` 전부. 파일 이름 순서라 결과가 결정적이다."""
    out: list[SeedConcept] = []
    for file in sorted(path.glob("*.json")):
        document = json.loads(file.read_text(encoding="utf-8"))
        parsed = parse_seed(document, file_name=file.name)
        log.info("초기 사전 %s: 개념 %d", file.name, len(parsed))
        out.extend(parsed)
    return tuple(out)


def apply_seed(config: Config, concepts: Iterable[SeedConcept]) -> SeedResult:
    """서비스 표에 넣는다. 한 연결, 한 트랜잭션. 모듈 docstring 의 "덮지 않는다" 규약."""
    concepts = tuple(concepts)
    new_concepts = 0
    new_expressions = 0
    ids: dict[tuple[str, str], int] = {}
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        for concept in concepts:
            cur.execute(
                f"""
                INSERT INTO {CONCEPT}
                    (canonical_name, display_ko, description, category, countable, source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (canonical_name, category) DO UPDATE
                   SET display_ko  = coalesce({CONCEPT}.display_ko,  EXCLUDED.display_ko),
                       description = coalesce({CONCEPT}.description, EXCLUDED.description),
                       updated_at  = now()
                RETURNING id, (xmax = 0)
                """,
                (
                    concept.canonical_name,
                    concept.display_ko,
                    concept.description,
                    concept.category,
                    concept.countable,
                    concept.source,
                ),
            )
            concept_id, inserted = cur.fetchone()
            # `wikidata:Q894874` → 종류와 식별자. 표현에는 나눠서 넣는다 — 종류만 적으면
            # 브랜드 1.4만 건과 이번에 부은 것이 한 값이 되어 출처 단위로 못 내린다.
            kind, _, source_id = concept.source.partition(":")
            ids[(concept.canonical_name.lower(), concept.category)] = int(concept_id)
            new_concepts += int(bool(inserted))
            for expression in concept.expressions:
                cur.execute(
                    f"""
                    INSERT INTO {EXPRESSION}
                        (concept_id, lang, surface, normalized, kind, source, source_id, license)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (lang, normalized, concept_id) DO NOTHING
                    """,
                    (
                        concept_id,
                        expression.lang,
                        expression.surface,
                        expression.normalized,
                        expression.kind,
                        kind,
                        source_id or None,
                        concept.license,
                    ),
                )
                new_expressions += cur.rowcount

        parents_set = 0
        for concept in concepts:
            if not concept.parent_name:
                continue
            parent_id = ids.get((concept.parent_name.lower(), concept.category))
            if parent_id is None:
                raise ValueError(
                    f"{concept.canonical_name}: 상위 {concept.parent_name!r} 가 "
                    "같은 파일·분류에 없다"
                )
            cur.execute(
                f"UPDATE {CONCEPT} SET parent_id = %s, updated_at = now() "
                f"WHERE id = %s AND parent_id IS NULL AND id <> %s",
                (parent_id, ids[(concept.canonical_name.lower(), concept.category)], parent_id),
            )
            parents_set += cur.rowcount
    result = SeedResult(len(concepts), new_concepts, new_expressions, parents_set)
    log.info(
        "초기 사전 적재: 개념 %d (새로 %d) · 표현 새로 %d · 상위 연결 %d",
        result.concepts_seen,
        result.concepts_new,
        result.expressions_new,
        result.parents_set,
    )
    return result


def apply_seed_in_memory(
    dictionary: Dictionary,
    concepts: Iterable[SeedConcept],
    *,
    rejected: AbstractSet[tuple[str, str, int]] = frozenset(),
) -> tuple[Dictionary, SeedResult]:
    """`apply_seed` 와 같은 규칙을 DB 가 아니라 메모리 사전에 적용한다 — 쓰지 않고 결과만 본다.

    사전을 대량으로 바꾸기 전에 전후를 비교하려면 **새 표현이 DB 에 들어가기 전의** 매핑
    결과가 있어야 한다. `apply_seed` 는 `--dry-run` 에서도 적재하므로(그래야 dry-run 이
    의미가 있다) 그 경로로는 되돌릴 수 없다. 여기서 만든 사전은 어디에도 쓰이지 않는다.

    **새 개념과 새 표현의 번호는 음수다.** DB 가 발행한 번호와 섞이지 않고 덤프에서 눈으로
    갈린다. 그래서 두 실행의 덤프를 개념 번호로 맞대면 안 되고 `(lang, normalized)` 로
    맞대야 한다 (`jobs/concept.py` 의 `--dump`).

    `rejected` 는 검수가 내린 `(lang, normalized, concept_id)` 다. 적재의
    `ON CONFLICT DO NOTHING` 이 REJECTED 행에도 걸려 그 쌍을 되살리지 않으므로 여기서도 뺀다.
    주지 않으면 실제 적재보다 표현이 더 는 것처럼 보인다 — 좋아 보이는 쪽으로 틀린다.
    """
    concepts = tuple(concepts)
    by_name: dict[tuple[str, str], int] = {}
    for concept in dictionary.concepts():
        key = (concept.canonical_name.lower(), concept.category)
        current = by_name.get(key)
        if current is None:
            by_name[key] = concept.concept_id
            continue
        # DB 의 유일키는 `(canonical_name, category)` 로 대소문자를 가리는데 이름 조회는
        # 소문자로 접는다. 둘이 어긋나 개념이 갈려 있으면 적재도 조회도 흔들린다.
        log.warning(
            "대표 이름이 대소문자만 다른 개념이 둘이다 — %s/%s (%d · %d)",
            concept.canonical_name, concept.category, current, concept.concept_id,
        )
        by_name[key] = min(current, concept.concept_id)

    merged: dict[int, Concept] = {c.concept_id: c for c in dictionary.concepts()}
    expressions: list[Expression] = list(dictionary.expressions())
    present = {(e.lang, e.normalized, e.concept_id) for e in expressions}
    next_concept_id = -1
    next_expression_id = -1
    new_concepts = 0
    new_expressions = 0
    ids: dict[tuple[str, str], int] = {}

    for concept in concepts:
        key = (concept.canonical_name.lower(), concept.category)
        concept_id = by_name.get(key)
        if concept_id is None:
            concept_id = next_concept_id
            next_concept_id -= 1
            by_name[key] = concept_id
            merged[concept_id] = Concept(
                concept_id=concept_id,
                canonical_name=concept.canonical_name,
                category=concept.category,
                countable=concept.countable,
            )
            new_concepts += 1
        ids[key] = concept_id
        for expression in concept.expressions:
            identity = (expression.lang, expression.normalized, concept_id)
            if identity in present or identity in rejected:
                continue
            present.add(identity)
            expressions.append(
                Expression(
                    expression_id=next_expression_id,
                    concept_id=concept_id,
                    lang=expression.lang,
                    normalized=expression.normalized,
                )
            )
            next_expression_id -= 1
            new_expressions += 1

    parents_set = 0
    for concept in concepts:
        if not concept.parent_name:
            continue
        parent_id = ids.get((concept.parent_name.lower(), concept.category))
        if parent_id is None:
            raise ValueError(
                f"{concept.canonical_name}: 상위 {concept.parent_name!r} 가 "
                "같은 파일·분류에 없다"
            )
        concept_id = ids[(concept.canonical_name.lower(), concept.category)]
        current = merged[concept_id]
        # 적재와 같은 조건 — 이미 상위가 있으면 덮지 않고 자기 자신은 상위가 못 된다.
        if current.parent_id is None and concept_id != parent_id:
            merged[concept_id] = replace(current, parent_id=parent_id)
            parents_set += 1

    # `ambiguous` 를 다시 센다. 적재 경로에서는 `io/concepts.EXPRESSIONS_SQL` 이 조회할 때마다
    # 세므로, 여기서 안 세면 **표현을 늘려 생긴 모호성이 안 보인다.** 그것이 이 비교의 핵심이다.
    holders: dict[tuple[str, str], set[int]] = {}
    for expression in expressions:
        holders.setdefault((expression.lang, expression.normalized), set()).add(
            expression.concept_id
        )
    expressions = [
        replace(
            expression,
            ambiguous=expression.ambiguous
            or len(holders[(expression.lang, expression.normalized)]) > 1,
        )
        for expression in expressions
    ]

    result = SeedResult(len(concepts), new_concepts, new_expressions, parents_set)
    log.info(
        "초기 사전 메모리 적용: 개념 %d (새로 %d) · 표현 새로 %d · 상위 연결 %d — 쓰지 않았다",
        result.concepts_seen,
        result.concepts_new,
        result.expressions_new,
        result.parents_set,
    )
    return Dictionary(merged.values(), expressions), result


def _expressions(labels: Mapping, aliases: Mapping) -> tuple[SeedExpression, ...]:
    out: list[SeedExpression] = []
    seen: set[tuple[str, str]] = set()

    def add(lang: str, surface, kind: str) -> None:
        text = _clean(surface)
        if not text:
            return
        key = concept_key(text)
        if not key or (lang, key) in seen:
            return
        seen.add((lang, key))
        out.append(SeedExpression(lang=lang, surface=text, normalized=key, kind=kind))

    add("en", labels.get("en"), KIND_CANONICAL)
    for lang, surface in labels.items():
        if lang != "en":
            add(str(lang), surface, KIND_SYNONYM)
    for lang, surfaces in aliases.items():
        for surface in surfaces or ():
            add(str(lang), surface, KIND_VARIANT)
    return tuple(out)


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
