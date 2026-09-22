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

**분류(`pl_concept.category`)로는 아무 유형도 거르지 않는다.** 2026-09-19 에 `RISING` 에서만
소재를 빼는 스위치(`rising.exclude_categories`)를 두었다가 2026-09-21 에 배선째 걷어냈다.
세 유형이 같은 키워드를 두고 다르게 답하면 화면에서 이상하게 보이고, 어차피 서버 코퍼스에서는
목록이 굶어 값을 비워 두고 있었다. `셔츠` · `바지` 같은 늘 흔한 말은 분류가 아니라 RISING
조건(증가율 · 증가량 · 언급량 · 소스 · z)이 막는다 — 후보 59개를 전부 확인했고 하나도 없었다.

**모호한 표기는 접지 않는다.** 한 표기가 두 개념에 걸리면(`크리스찬 디올` 이 designer 이자
brand) 어느 쪽으로 합쳐도 틀린다. `io/concepts.EXPRESSIONS_SQL` 이 쓰는 규약과 같다 — 칸을
믿지 않고 실제로 몇 개념에 걸리는지 다시 세어 걸린 것은 혼자 둔다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConceptRef:
    """키워드 하나가 붙은 개념. `io/metrics.concept_groups()` 가 돌려주는 행이다."""

    keyword_id: int
    concept_id: int
    # `false` 면 세지 않는 일반 단어다. 지표 행은 그대로 쓰되 순위와 배지를 주지 않는다.
    countable: bool


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
) -> Grouping:
    """개념 행 → 접기 규칙.

    `weights` 는 대표를 고르는 데 쓰는 무게이고 **지평 전체의 언급량**이다. 기간마다 다시
    고르지 않는다 — `24H` 에서는 `가죽` 이, `30D` 에서는 `leather` 가 대표가 되면 같은 개념이
    화면마다 다른 이름으로 나온다. 무게가 같으면 `keyword_id` 가 작은 쪽으로 정해 실행마다
    결과가 같게 한다.

    `keywords` 는 이번 회차에 원자료가 있는 키워드다. 거기 없는 것은 그룹에서 빼고 센다 —
    지표 행이 만들어지지 않을 키워드를 대표로 뽑으면 그 개념이 통째로 순위에서 사라진다.
    """
    # 한 표기가 두 개념에 걸리면 어느 쪽으로도 접지 않는다 (머리말의 모호 규약).
    seen: dict[int, set[int]] = {}
    for ref in refs:
        seen.setdefault(ref.keyword_id, set()).add(ref.concept_id)
    ambiguous = {keyword_id for keyword_id, ids in seen.items() if len(ids) > 1}

    members: dict[int, list[int]] = {}
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

    representative: dict[int, int] = {}
    for group in members.values():
        if len(group) < 2:
            continue
        leader = max(group, key=lambda keyword_id: (weights.get(keyword_id, 0), -keyword_id))
        for keyword_id in group:
            if keyword_id != leader:
                representative[keyword_id] = leader
    return Grouping(representative=representative, silenced=frozenset(silenced))

