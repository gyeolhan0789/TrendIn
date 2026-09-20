"""(언어, 비교키) → 개념. 메모리에 올린 표현 사전.

개념 수천 · 표현 수만이면 전부 메모리에 있어도 수십 MB 다. 기사마다 DB 를 치지 않고 한 번
읽어 두고 조회만 한다 — 조회 경로는 Spark UDF 안이 아니라 드라이버다 (`jobs/concept.py`).

## 조회 규칙

| 표기의 문자 체계 | 1차 | 2차 |
| --- | --- | --- |
| 한글 · 가나 · 아랍 | `(lang, key)` | `key` 만으로 (언어 칸이 잘못 붙은 경우의 안전망) |
| 라틴 | `key` — **언어 무관** | `latin_fold(key)` — 악센트를 접은 2차 키 |

라틴 표기를 언어 무관으로 보는 이유는 브랜드다. `Gucci` 는 영어·프랑스어·이탈리아어 기사에서
같은 글자이고, 한국·일본 기사 안에도 그대로 박혀 나온다. 기사 언어로 가르면 같은 표기가 네
키로 갈린다. 대가는 `coach`(브랜드) 와 `coach`(코치) 를 언어로 못 가른다는 것인데, 그건 어차피
영어 안에서도 못 가르는 문제라 `ambiguous` 와 문맥이 맡는다 (`mapping.disambiguate`).

**한 개념에 여러 표현이 걸려도 결과는 개념당 하나다.** 부른 쪽이 "어느 개념이냐" 를 묻는
것이고 어느 표현으로 붙었는지는 근거로만 남긴다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from trendin.spark.concept.normalize import LATIN, latin_fold, script_of


@dataclass(frozen=True, slots=True)
class Concept:
    concept_id: int
    canonical_name: str
    category: str
    parent_id: int | None = None
    # False 면 "기억은 하되 세지 않는" 일반 단어다. 사전에 두는 이유는 매일 미등록으로 다시
    # 올라오지 않게 하려는 것이고, 랭킹이 이 값을 보고 거른다.
    countable: bool = True


@dataclass(frozen=True, slots=True)
class Expression:
    expression_id: int
    concept_id: int
    lang: str
    normalized: str
    # 같은 (lang, normalized) 가 다른 개념에도 걸려 있다. 조회가 둘 이상을 돌려주면 문맥 판정.
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class Hit:
    expression: Expression
    concept: Concept


class Dictionary:
    """표현 사전. 만들 때 색인을 다 세우고 그 뒤로는 읽기만 한다."""

    def __init__(self, concepts: Iterable[Concept], expressions: Iterable[Expression]) -> None:
        self._concepts: dict[int, Concept] = {c.concept_id: c for c in concepts}
        self._by_lang: dict[tuple[str, str], list[Expression]] = defaultdict(list)
        self._by_key: dict[str, list[Expression]] = defaultdict(list)
        self._latin_folded: dict[str, list[Expression]] = defaultdict(list)
        self._expressions: list[Expression] = []
        self._size = 0
        for expression in expressions:
            if expression.concept_id not in self._concepts:
                # 개념이 없는 표현은 사전에 없는 것과 같다. 조용히 빼면 나중에 "왜 안 붙나" 를
                # 찾을 수 없으므로 여기서 죽는다 — 적재가 개념을 먼저 넣어야 한다.
                raise KeyError(
                    f"표현 {expression.expression_id} 의 개념 {expression.concept_id} 이 "
                    "사전에 없다"
                )
            self._expressions.append(expression)
            self._by_lang[(expression.lang, expression.normalized)].append(expression)
            self._by_key[expression.normalized].append(expression)
            if script_of(expression.normalized) == LATIN:
                self._latin_folded[latin_fold(expression.normalized)].append(expression)
            self._size += 1

    def __len__(self) -> int:
        return self._size

    def concept(self, concept_id: int) -> Concept:
        return self._concepts[concept_id]

    def concepts(self) -> tuple[Concept, ...]:
        return tuple(self._concepts.values())

    def expressions(self) -> tuple[Expression, ...]:
        """사전의 표현 전부. 후보 생성기가 자기 색인을 세울 때 한 번 훑는다."""
        return tuple(self._expressions)

    def lookup(self, lang: str, key: str) -> tuple[Hit, ...]:
        """이 표기가 가리킬 수 있는 개념 전부. 없으면 빈 튜플, 둘 이상이면 모호하다.

        개념 번호 순으로 정렬해 돌려준다 — 같은 입력에 같은 순서가 나와야 유보 기록의 diff 가
        읽힌다.
        """
        if not key:
            return ()
        if script_of(key) == LATIN:
            found = self._by_key.get(key) or self._latin_folded.get(latin_fold(key)) or ()
        else:
            found = self._by_lang.get((lang, key)) or self._by_key.get(key) or ()
        by_concept: dict[int, Expression] = {}
        for expression in found:
            # 한 개념에 표현이 여럿이면 번호가 작은 것 하나를 근거로 남긴다.
            current = by_concept.get(expression.concept_id)
            if current is None or expression.expression_id < current.expression_id:
                by_concept[expression.concept_id] = expression
        return tuple(
            Hit(expression=by_concept[cid], concept=self._concepts[cid])
            for cid in sorted(by_concept)
        )
