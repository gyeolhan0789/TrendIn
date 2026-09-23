"""기사 하나의 키워드 목록 → 기사별 개념 행 · 미등록 · 유보.

LLM 을 부르지 않는다. 사전에 있으면 붙이고, 없으면 미등록으로 내보내고, 둘 이상에 걸리면
기사 안의 다른 개념들로 갈라 보고 안 갈리면 유보한다. **세지 않는 쪽이 잘못 세는 쪽보다
낫다** — 유보는 그 기사에서 그 표기를 개념에 붙이지 않는다는 뜻이고, 기록은 남긴다.

## 결과가 기사·개념 한 쌍에 한 행인 이유

한 기사에 `부츠` 와 `boots` 가 같이 나와도 개념 `boots` 는 그 기사에서 **한 번** 언급된 것이다.
집계 단위가 "개념을 언급한 기사 수" 라서 여기서 접어야 랭킹이 `count(*)` 만 해도 맞다.
어느 표현들이 붙였는지는 `expression_ids` 로 남겨 오류 추적과 영향 범위 계산에 쓴다.

## 모호한 표기를 가르는 규칙 (MVP)

기사 안에서 **모호하지 않게** 붙은 개념들의 분류를 본다.

1. 후보 중 그 분류 집합에 드는 것이 딱 하나면 그것.
2. 아니면, 후보 중 패션 분류인 것이 딱 하나이고 기사에 패션 개념이 하나라도 붙어 있으면 그것.
   `코트` 가 외투(apparel)와 경기장(sports)에 걸렸고 기사에 신발·브랜드가 있으면 외투다.
3. 그래도 안 갈리면 유보.

문맥 문장으로 LLM 에 묻는 것은 다음 단계다. 이 규칙은 그 전에 싸게 갈리는 것만 가른다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from trendin.spark.concept.dictionary import Concept, Dictionary, Hit
from trendin.spark.concept.normalize import concept_key, lang_of_surface

METHOD_DICT = "DICT"
METHOD_CONTEXT = "CONTEXT"

# 패션으로 세는 분류. `pl_concept_category` 의 초기값 중 여기 없는 것이 둘이다 — `generic` 은
# 일반 단어라서, `person` 은 **다른 축**이라서다. 연예인이 나왔다는 것은 그 기사가 패션
# 기사라는 근거이지 `코트` 가 외투인지 경기장인지를 가르는 근거가 아니다.
FASHION_CATEGORIES = frozenset(
    {"apparel", "footwear", "accessory", "material", "color", "style", "brand", "designer"}
)


@dataclass(frozen=True, slots=True)
class Keyword:
    """추출이 넘긴 표기 하나 (계약 A 의 `keywords[]` 한 칸)."""

    surface: str
    context: str | None = None


@dataclass(frozen=True, slots=True)
class ConceptRow:
    article_id: int
    concept_id: int
    expression_ids: tuple[int, ...]
    method: str


@dataclass(frozen=True, slots=True)
class Unmapped:
    article_id: int
    lang: str
    normalized: str
    surface: str
    context: str | None

    @property
    def key(self) -> tuple[str, str]:
        """표현을 가리키는 열쇠. 판정·문맥·미등록 표가 같은 쌍을 쓴다."""
        return (self.lang, self.normalized)


@dataclass(frozen=True, slots=True)
class Deferred:
    article_id: int
    lang: str
    normalized: str
    concept_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MappingResult:
    rows: tuple[ConceptRow, ...]
    unmapped: tuple[Unmapped, ...]
    deferred: tuple[Deferred, ...]
    # 모호하지 않게 붙은 표기. 이것만 검수 대기에서 내린다 (`io/concepts.RESOLVE_MAPPED_SQL`).
    resolved_keys: tuple[tuple[str, str], ...]
    # 모호했지만 문맥 규칙이 갈라 붙인 표기. **`resolved_keys` 와 일부러 나눠 둔다** —
    # 붙기는 붙었으므로 기사에는 개념이 남지만, 규칙이 추측한 것이라 검수 대기에서는 내리지
    # 않는다. 나누지 않으면 사전 변경 전후를 맞댈 때 이 표기들이 셋 중 어디에도 없어
    # "말뭉치가 달라졌다" 로 잘못 세어진다 (`jobs/concept.py` 의 `--dump`).
    context_keys: tuple[tuple[str, str], ...] = ()


def map_article(
    article_id: int,
    article_lang: str | None,
    keywords: Iterable[Keyword],
    dictionary: Dictionary,
) -> MappingResult:
    """두 번 지난다. 먼저 모호하지 않은 것을 붙이고, 그 결과로 모호한 것을 가른다."""
    resolved: dict[int, set[int]] = {}  # concept_id -> expression_ids
    methods: dict[int, str] = {}
    pending: list[tuple[str, str, tuple[Hit, ...]]] = []
    unmapped: list[Unmapped] = []
    resolved_keys: set[tuple[str, str]] = set()
    seen_keys: set[tuple[str, str]] = set()

    for keyword in keywords:
        key = concept_key(keyword.surface)
        if not key:
            continue
        lang = lang_of_surface(keyword.surface, article_lang)
        if (lang, key) in seen_keys:
            continue  # 같은 표기가 기사에 여러 번 — 한 번만 본다
        seen_keys.add((lang, key))

        hits = dictionary.lookup(lang, key)
        if not hits:
            unmapped.append(Unmapped(article_id, lang, key, keyword.surface, keyword.context))
        elif len(hits) == 1:
            _attach(resolved, methods, hits[0], METHOD_DICT)
            resolved_keys.add((lang, key))
        else:
            pending.append((lang, key, hits))

    deferred: list[Deferred] = []
    context_keys: set[tuple[str, str]] = set()
    for lang, key, hits in pending:
        chosen = disambiguate(hits, {cid: dictionary.concept(cid) for cid in resolved})
        if chosen is None:
            deferred.append(
                Deferred(article_id, lang, key, tuple(h.concept.concept_id for h in hits))
            )
        else:
            _attach(resolved, methods, chosen, METHOD_CONTEXT)
            context_keys.add((lang, key))

    rows = tuple(
        ConceptRow(article_id, cid, tuple(sorted(resolved[cid])), methods[cid])
        for cid in sorted(resolved)
    )
    return MappingResult(
        rows=rows,
        unmapped=tuple(unmapped),
        deferred=tuple(deferred),
        resolved_keys=tuple(sorted(resolved_keys)),
        context_keys=tuple(sorted(context_keys)),
    )


def disambiguate(hits: tuple[Hit, ...], resolved: Mapping[int, Concept]) -> Hit | None:
    """모듈 docstring 의 세 규칙. 어느 것도 안 맞으면 `None`."""
    categories = {concept.category for concept in resolved.values()}
    same_category = [h for h in hits if h.concept.category in categories]
    if len(same_category) == 1:
        return same_category[0]
    if len(same_category) > 1:
        # 기사가 두 후보의 분류를 다 갖고 있다 — 진짜 모호하다. 패션 규칙으로 내려가면
        # 안 된다: 그 규칙은 근거가 **없을** 때의 기본값이고, 여기는 근거가 서로 부딪히는 경우다.
        return None
    if categories & FASHION_CATEGORIES:
        fashion = [h for h in hits if h.concept.category in FASHION_CATEGORIES]
        if len(fashion) == 1:
            return fashion[0]
    return None


def _attach(resolved: dict[int, set[int]], methods: dict[int, str], hit: Hit, method: str) -> None:
    cid = hit.concept.concept_id
    resolved.setdefault(cid, set()).add(hit.expression.expression_id)
    # DICT 로 한 번 붙은 개념에 CONTEXT 근거가 더해져도 방법은 DICT 로 남는다 — 더 강한 근거다.
    if cid not in methods or method == METHOD_DICT:
        methods[cid] = method
