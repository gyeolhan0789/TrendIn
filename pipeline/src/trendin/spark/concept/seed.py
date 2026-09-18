"""초기 사전 — `spark/conf/concepts/*.json` 을 읽어 `concept` · `concept_expression` 에 넣는다.

## 파일 모양

```json
{
  "source": "wikidata",          // 또는 "seed" (손으로 만든 것)
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

## 사람이 고친 것을 덮지 않는다

초기 사전은 **다시 넣어도 안전해야** 한다 (위키데이터는 한 달에 한 번쯤 갱신한다). 그래서
개념 upsert 는 비어 있는 칸만 채우고(`coalesce`), 표현은 이미 있으면 건드리지 않는다 —
검수자가 `REJECTED` 로 내린 표현이 다음 초기 사전 적재에 되살아나면 안 된다.

**pyspark 를 import 하지 않는다** (층 1). `apply_seed` 만 DB 를 친다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.concept.normalize import concept_key
from trendin.spark.io import jdbc
from trendin.spark.io.concepts import CONCEPT, EXPRESSION

log = get_logger(__name__)

KIND_CANONICAL = "canonical"
KIND_SYNONYM = "synonym"
KIND_VARIANT = "variant"

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
    if source not in ("wikidata", "seed"):
        raise ValueError(f"{file_name}: source 는 wikidata 또는 seed 여야 한다: {source!r}")
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
            ids[(concept.canonical_name.lower(), concept.category)] = int(concept_id)
            new_concepts += int(bool(inserted))
            for expression in concept.expressions:
                cur.execute(
                    f"""
                    INSERT INTO {EXPRESSION} (concept_id, lang, surface, normalized, kind, source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (lang, normalized, concept_id) DO NOTHING
                    """,
                    (
                        concept_id,
                        expression.lang,
                        expression.surface,
                        expression.normalized,
                        expression.kind,
                        concept.source.split(":", 1)[0],
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
