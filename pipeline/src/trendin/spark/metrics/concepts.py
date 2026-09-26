"""개념 단위 순위 — 같은 것의 다른 표기를 한 자리로 접고, 세지 않을 개념을 뺀다.

**왜 집계가 개념을 읽는가.** 순위표는 자리가 다섯이다 (`current.top_n`). 그 다섯 자리를
같은 개념의 다른 언어 표기가 나눠 먹으면, 실제로 보여줄 수 있는 것이 다섯보다 적어진다.
2026-09-19 실측(fashion 3개월)에서 **30D 상위 100 표기가 실제로는 82 개념**이었다 —

| 개념 | 흩어진 표기 | 합산 | 흩어진 순위 |
| --- | --- | --- | --- |
| leather | leather · pelle · 가죽 · cuir | 454 | 8 · 11 · 34 · 59 |
| jeans | jeans · 청바지 · 데님 팬츠 | 386 | 3 · 30 · 79 |
| Vogue | Vogue · Vogue Italia · British Vogue | 358 | 4 · 43 · 57 |

합치면 1위인 것이 넷으로 쪼개져 아무 자리도 제대로 차지하지 못한다. 접는 일 자체는 [05] 의
병합이 이미 하지만 그건 **같은 언어 안의 표기 변형**까지다 — 언어가 다르면 편집 거리도 음차
유사도도 성립하지 않아([05 §3]) 개념 사전이 답하는 수밖에 없다.

**`countable` 이 무정보어를 거른다** (`pl_concept.countable`, [개념층] 의 "세지 않는 일반
단어"). 사전이 이미 그 축을 들고 있었고 집계가 읽지 않고 있었다. 그 칸이 빼는 것은 세 갈래다 —

* 일반어: `collection` · `texture` · `style` · `요즘` · `매력`, 그리고 대명사(`she` 개념이
  `he`·`you`·`they` 까지 한 묶음으로 들고 있다)
* 총칭: `clothing` · `tops` · `outerwear` · `fabric` · `shoes` — 범주 자체를 가리키는 말
* 출처: `Vogue` · `Elle` · `GQ` · `Instagram` 같은 매체와 유통 채널. 패션 트렌드가 아니라
  그 트렌드를 **말하는 쪽**이라 순위표에 있으면 자리만 차지한다

**z 하한은 이 일을 못 한다.** 2026-09-19 에 재 보고 방향을 바꿨다 — 30D 에서 `샤넬` 이 z=0.00
이고 `collection` 이 1.59, `suede` 가 2.72 였다. z 는 "흔한 말인가" 가 아니라 "배경 대비 최근에
튀었나" 를 재므로, 꾸준한 진짜 브랜드가 먼저 떨어지고 시즌 따라 늘어나는 배경어가 남는다.
`RISING` 에서 z 가 제 몫을 하는 것과 `CURRENT` 에서 쓸 수 있는 것은 별개였다.

**분류(`pl_concept.category`)로 유형별로 거르지는 않는다.** 2026-09-19 에 `RISING` 에서만
소재를 빼는 스위치(`rising.exclude_categories`)를 두었다가 2026-09-21 에 배선째 걷어냈다.
세 유형이 같은 키워드를 두고 다르게 답하면 화면에서 이상하게 보이고, 어차피 서버 코퍼스에서는
목록이 굶어 값을 비워 두고 있었다. **분류째 모든 유형에서 빼는 것은 한다** —
`aggregate.concepts.hide_categories` 에 적은 분류(인물 · 행사)는 세지 않는 개념과 똑같이
순위와 배지에서 빠진다 (`batch.load_grouping`). 세 유형이 같은 답을 내므로 위 문제가 없다.
`셔츠` · `바지` 같은 늘 흔한 말은 분류가 아니라 RISING 조건(증가율 · 증가량 · 언급량 · 소스
· z)이 막는다 — 후보 59개를 전부 확인했고 하나도 없었다.

**모호한 표기는 접지 않는다.** 한 표기가 두 개념에 걸리면(`크리스찬 디올` 이 designer 이자
brand) 어느 쪽으로 합쳐도 틀린다. `io/concepts.EXPRESSIONS_SQL` 이 쓰는 규약과 같다 — 칸을
믿지 않고 실제로 몇 개념에 걸리는지 다시 세어 걸린 것은 혼자 둔다.

**연도·시즌만 다른 표기도 접는다** (S15P21A102-385, `registry/edition.py`). 사전에 없던 새
이름이 여러 변형으로 한꺼번에 들어오면 개념이 없어 위 규칙이 아무것도 못 한다 — 2026-09-24
24H 순위 1~4위가 `Vogue World` · `Vogue World 2026` · `Vogue World Milano 2026` ·
`Vogue World: Milano` 였다. 연도·시즌을 뗀 기준형이 같은 키워드끼리 한 덩이로 둔다.

**같은 것이 아니라 같은 집계 단위다.** `Vogue World 2026` 은 시리즈의 한 회차라 표기 병합
(`pl_alias`)으로 영구히 붙이지 않고 여기서만 합친다. 키워드가 그대로라 되돌릴 수 있고, 이미
승격된 키워드에도 걸리며, 기준형 키워드가 없어도 회차끼리(`met gala 2026` · `met gala 2027`) 접는다.

**합산과 보이는 이름은 다른 문제다.** 연도·시즌을 떼서 합산하는 것은 보수적인 문자열 규칙이고,
최신 회차를 이름으로 내는 것은 **행사(`event`) 개념이 확인된 덩이에만** 한다. `Saint Laurent` 과
`Saint Laurent SS27` 을 합산해도 이름은 브랜드여야 하고, 사전 분류에 장소가 없어 개념이 없는 덩이
(`Los Angeles` · `Los Angeles 2028`)는 도시인지 행사인지 모른다. 그런 덩이는 개념 접기처럼
무게로 고른다.

행사 덩이의 대표는 이 차례로 고른다 —

1. 덩이 전체 언급량의 `representative_min_share` 이상인 회차만 후보다 — 예고 기사 한 건
   (`Vogue World 2027`)이 이름을 가져가지 못하게
2. 연도·시즌이 가장 늦은 것 (`fw26` < `rs27` < `ss27`)
3. 같으면 기준형이 짧은 것 — `vogue world 2026` 이 `vogue world milano 2026` 을 이긴다
4. 그다음 언급량, 마지막으로 id

1~3 이 이름에서 정해지므로 언급량이 오르내려도 대표가 흔들리지 않는다. 후보가 없으면 무게로 고른다.

개념·판정과 부딪칠 때의 차례 —

1. 한 덩이가 **서로 다른 두 개념**에 걸리면 접지 않는다. 사전이 이긴다 (모호 규약과 같은 이유)
2. 덩이 안에 **세지 않는** 표기가 있으면 덩이 전체를 뺀다. `vogue world` 가 제외됐는데
   `vogue world 2026` 이 순위로 돌아오면 제외 판정을 우회한 것이다
3. 단 덩이 안에 **세는 개념**에 붙은 표기가 있으면 2 를 하지 않고 접지도 않는다 — 사전이
   세라고 한 것을 판정 하나가 덮지 않는다

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass

# 최신 회차를 보이는 이름으로 낼 수 있는 개념 분류 (`concept/seed.CATEGORIES`).
EVENT = "event"


@dataclass(frozen=True, slots=True)
class ConceptRef:
    """키워드 하나가 붙은 개념. `io/metrics.concept_groups()` 가 돌려주는 행이다."""

    keyword_id: int
    concept_id: int
    # `false` 면 세지 않는 일반 단어다. 지표 행은 그대로 쓰되 순위와 배지를 주지 않는다.
    countable: bool
    # `pl_concept.category`. 보이는 이름을 고르는 데만 쓴다 — `event` 덩이만 최신 회차를 낸다.
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Grouping:
    """어느 키워드를 어디로 접고 무엇을 세지 않는지.

    **`representative` 에 없는 키워드는 접히지 않은 것이다** — 개념 매핑이 없거나, 모호해서
    혼자 두기로 한 것이다. 그런 키워드는 지금까지처럼 자기 값으로 순위에 든다. 개념 층을
    아직 돌리지 않은 환경에서 이 자료구조가 통째로 비면 집계가 옛 동작 그대로 돈다.
    """

    # 흡수된 keyword_id → 대표 keyword_id. **대표 자신은 여기 없다.**
    representative: dict[int, int]
    # 순위와 배지를 주지 않을 keyword_id. `countable = false` 인 개념에 붙은 것 전부다.
    silenced: frozenset[int]
    # 연도·시즌 규칙이 이번에 접은 표기 수. `representative` 에 이미 들어 있고 로그용이다.
    edition_folded: int = 0

    @property
    def folded(self) -> int:
        """접힌 표기 수 — 순위표에서 되찾은 자리의 수와 같다."""
        return len(self.representative)

    def members_of(self, representative: int) -> tuple[int, ...]:
        """그 대표가 흡수한 keyword_id 들. 대표 자신은 넣지 않는다."""
        return tuple(
            keyword_id
            for keyword_id, target in self.representative.items()
            if target == representative
        )


def build_grouping(
    refs: list[ConceptRef],
    weights: dict[int, int],
    *,
    keywords: set[int],
    silenced_keywords: frozenset[int] = frozenset(),
    edition_keys: Mapping[int, Hashable] | None = None,
    edition_orders: Mapping[int, tuple[int, ...]] | None = None,
    representative_min_share: float = 0.0,
) -> Grouping:
    """개념 행 → 접기 규칙.

    `weights` 는 대표를 고르는 데 쓰는 무게이고 **지평 전체의 언급량**이다. 기간마다 다시
    고르지 않는다 — `24H` 에서는 `가죽` 이, `30D` 에서는 `leather` 가 대표가 되면 같은 개념이
    화면마다 다른 이름으로 나온다. 무게가 같으면 `keyword_id` 가 작은 쪽으로 정해 실행마다
    결과가 같게 한다.

    `keywords` 는 이번 회차에 원자료가 있는 키워드다. 거기 없는 것은 그룹에서 빼고 센다 —
    지표 행이 만들어지지 않을 키워드를 대표로 뽑으면 그 개념이 통째로 순위에서 사라진다.

    `edition_keys` 는 `keyword_id → 연도·시즌 덩이 열쇠` 다 (`registry/edition.edition_key`
    를 도메인과 묶은 값). 열쇠가 같은 키워드가 한 덩이다. 비우면 개념으로만 접는다.
    `edition_orders` 는 회차인 키워드의 순서 열쇠다 — `(연도, 시즌 순위, -기준형 낱말 수)`.
    대표를 고르는 데만 쓰고, **행사 개념이 있는 덩이에서만** 읽는다 (머리말).
    """
    # 한 표기가 두 개념에 걸리면 어느 쪽으로도 접지 않는다 (머리말의 모호 규약).
    seen: dict[int, set[int]] = {}
    for ref in refs:
        seen.setdefault(ref.keyword_id, set()).add(ref.concept_id)
    ambiguous = {keyword_id for keyword_id, ids in seen.items() if len(ids) > 1}

    members: dict[int, list[int]] = {}
    events = {ref.concept_id for ref in refs if ref.category == EVENT}
    # 개념이 아직 없어 `countable` 을 걸 자리가 없는 표기다. 세지 않기로 판정된 것들이라
    # 접을 대상도 아니다 — `Vogue Italia` 를 어디에 접겠는가.
    silenced: set[int] = {keyword_id for keyword_id in silenced_keywords if keyword_id in keywords}
    for ref in refs:
        if ref.keyword_id in ambiguous or ref.keyword_id not in keywords:
            continue
        if ref.keyword_id in silenced:
            continue
        if not ref.countable:
            # 세지 않는 개념은 접지도 않는다. 접어 봐야 순위에 들지 않을 행 하나를 더
            # 만들 뿐이고, 흡수된 표기의 지표만 대표 쪽으로 옮겨 상세 화면이 빈다.
            silenced.add(ref.keyword_id)
            continue
        members.setdefault(ref.concept_id, []).append(ref.keyword_id)

    groups = list(members.values())
    edition_folded = 0
    if edition_keys:
        groups, edition_folded, edition_silenced = _join_editions(
            groups,
            edition_keys,
            keywords=keywords,
            ambiguous=ambiguous,
            silenced=silenced,
        )
        silenced |= edition_silenced

    orders = edition_orders or {}
    event_members = {
        keyword_id
        for concept_id, group in members.items()
        if concept_id in events
        for keyword_id in group
    }
    representative: dict[int, int] = {}
    for group in groups:
        if len(group) < 2:
            continue
        leader = _leader(
            group,
            weights,
            orders if any(keyword_id in event_members for keyword_id in group) else {},
            min_share=representative_min_share,
        )
        for keyword_id in group:
            if keyword_id != leader:
                representative[keyword_id] = leader
    return Grouping(
        representative=representative,
        silenced=frozenset(silenced),
        edition_folded=edition_folded,
    )


def _leader(
    group: list[int],
    weights: dict[int, int],
    orders: Mapping[int, tuple[int, ...]],
    *,
    min_share: float,
) -> int:
    """덩이의 대표. `orders` 가 비면 무게가 큰 것, 같으면 id 가 작은 것.

    `orders` 가 있으면(행사 덩이) 덩이 전체의 `min_share` 이상인 회차 중 가장 늦은 회차다.
    """
    total = sum(weights.get(keyword_id, 0) for keyword_id in group)
    editions = [
        keyword_id
        for keyword_id in group
        if keyword_id in orders and weights.get(keyword_id, 0) >= min_share * total
    ]
    if editions:
        return max(
            editions,
            key=lambda keyword_id: (orders[keyword_id], weights.get(keyword_id, 0), -keyword_id),
        )
    return max(group, key=lambda keyword_id: (weights.get(keyword_id, 0), -keyword_id))


def _join_editions(
    concept_groups: list[list[int]],
    edition_keys: Mapping[int, Hashable],
    *,
    keywords: set[int],
    ambiguous: set[int],
    silenced: set[int],
) -> tuple[list[list[int]], int, set[int]]:
    """개념 덩이에 연도·시즌 덩이를 잇는다. 이은 덩이 목록 · 이 규칙이 더 접은 수 · 더 뺀 키워드.

    한 키워드는 개념 하나, 연도 덩이 하나에만 속하므로 **두 개념이 이어지는 길은 한 연도 덩이가
    두 개념에 걸리는 것뿐이다.** 그 덩이만 건너뛰면 어느 결과 덩이에도 개념이 둘 들지 않는다.
    `concept_groups` 에는 세는 개념만 들어 있다 — 세지 않는 것은 `silenced` 에 있다.
    """
    concept_of = {
        keyword_id: index
        for index, group in enumerate(concept_groups)
        for keyword_id in group
    }
    by_key: dict[Hashable, list[int]] = {}
    for keyword_id in sorted(keywords):
        if keyword_id in ambiguous or keyword_id not in edition_keys:
            continue
        by_key.setdefault(edition_keys[keyword_id], []).append(keyword_id)

    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        low, high = sorted((find(left), find(right)))
        if low != high:
            parent[high] = low

    for group in concept_groups:
        for keyword_id in group:
            union(group[0], keyword_id)
    extra_silenced: set[int] = set()
    for edition in by_key.values():
        if len(edition) < 2:
            continue
        touched = {concept_of[keyword_id] for keyword_id in edition if keyword_id in concept_of}
        if len(touched) > 1:
            continue
        if any(keyword_id in silenced for keyword_id in edition):
            # 세는 개념에 붙은 표기가 있으면 사전이 이긴다 — 빼지도 접지도 않는다.
            if not touched:
                extra_silenced.update(
                    keyword_id for keyword_id in edition if keyword_id not in silenced
                )
            continue
        for keyword_id in edition:
            union(edition[0], keyword_id)

    joined: dict[int, list[int]] = {}
    for node in sorted(parent):
        joined.setdefault(find(node), []).append(node)
    # 이 규칙이 새로 접은 표기 — 개념만으로는 대표에 접히지 않았을 것.
    concept_folded = sum(len(group) - 1 for group in concept_groups if len(group) > 1)
    total_folded = sum(len(group) - 1 for group in joined.values() if len(group) > 1)
    return list(joined.values()), total_folded - concept_folded, extra_silenced

