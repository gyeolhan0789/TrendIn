"""병합 쌍 → 대표 하나 ([05 §1] "통합을 끝낸 다음, 대표 하나만 `keywords` 에 넣는다").

층 1·2 가 낸 쌍은 **방향이 있지만 서로 엮인다.** `mcp → model context protocol` 과
`model contex protocol → model context protocol` 이 함께 나오면 셋이 한 덩이다. 그래서
쌍을 그래프로 보고 연결 요소마다 대표 하나를 고른다 (union-find).

| 산출물 | 담는 것 | 표 |
| --- | --- | --- |
| `aliases` | 별칭 → 대표. **해소된 결과** | `pl_alias` |
| `parked` | 자동 적용하지 않고 검수 큐로 보낼 쌍 | `pl_review_queue` |

**이미 승격된 키워드끼리는 자동 병합하지 않는다** ([05 §7]). 그건 [05 §1] 의 사후 병합이라
`member_interest_keywords` 이관과 삭제가 따라오고, 그 절차는 백엔드와 함께 수동으로 한다.
여기서는 큐에 남기고 넘어간다.

**한 덩이에 승격된 것이 둘 이상이면 그 덩이는 통째로 보류한다.** 사슬로 이어져
`a(승격) — b — c(승격)` 이 되는 경우다. `b` 만 어느 한쪽에 붙이는 것도 가능하지만, 그
선택이 곧 "a 와 c 는 별개다" 라는 판단이고 증거는 그 반대를 말하고 있다. **의심스러우면
보류한다** ([05 §5]).

**덩이가 `max_group_size` 보다 크면 통째로 보류하고 검수 큐에도 보내지 않는다.** 차단기다 —
정확도를 만드는 규칙이 아니라, union-find 가 만든 전이성이 폭주할 때의 마지막 방어선이다.
2026-09-20 운영에서 오타 쌍이 `chanel ← camel ← bagel → bague → vogue` 처럼 1건짜리 낱말을
징검다리로 이어져 한 덩이가 6,461개가 됐고, DF 최대인 `vogue`(매체)가 대표가 되어 브랜드가
순위에서 사라졌다 (S15P21A102-398). 그 크기의 덩이는 사람이 쌍 단위로 판단할 수 있는 것이
아니라 큐에 넣지 않는다 — 건수는 `oversized` 로 돌려주고 호출부가 지표와 로그로 남긴다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from trendin.spark.registry.merge import MergePair


@dataclass(frozen=True, slots=True)
class Alias:
    """`pl_alias` 한 줄. 근거는 이 별칭을 덩이에 붙인 쌍에서 온다.

    사슬로 붙은 별칭의 근거는 **직접 이웃과의 쌍**이다. 덩이 전체의 근거는 `pl_merge_log`
    가 쌍 단위로 남기므로, 둘을 함께 보면 판단을 재구성할 수 있다 ([05 §8]).
    """

    domain: str
    alias_key: str
    canonical_key: str
    layer: int
    rule: str
    confidence: float
    signal: str


@dataclass(frozen=True, slots=True)
class AliasResolution:
    aliases: tuple[Alias, ...]
    # 자동 적용하지 않은 쌍. 검수 큐로 간다.
    parked: tuple[MergePair, ...]
    # 실제로 병합이 일어난 덩이 수. 통계로 남긴다.
    merged_groups: int
    # 크기 상한을 넘어 통째로 보류한 덩이. `(DF 최대 구성원, 크기)` — 큐로 가지 않는다.
    oversized: tuple[tuple[str, int], ...] = ()


def resolve(
    pairs: Iterable[MergePair],
    *,
    df: Mapping[str, int],
    max_group_size: int,
    promoted: Collection[str] = (),
) -> AliasResolution:
    """쌍 목록을 별칭 표로 접는다.

    대표는 **DF 가 가장 높은 것**이고 동률은 사전순이다 — 실행마다 대표가 바뀌면
    `keywords.name` 이 흔들린다. 단 덩이에 승격된 것이 하나 있으면 **그것이 대표다.**
    DF 가 더 높은 별칭이 있어도 바꾸지 않는다 — 대표를 옮기면 이미 발급된 `keyword_id`
    를 버려야 하고 그건 사후 병합이다.
    """
    promoted_set = {key for key in promoted}
    accepted: list[MergePair] = []
    parked: list[MergePair] = []
    for pair in sorted(pairs, key=_pair_order):
        if pair.representative == pair.absorbed:
            continue
        if pair.representative in promoted_set and pair.absorbed in promoted_set:
            parked.append(pair)
            continue
        accepted.append(pair)

    parent: dict[str, str] = {}
    for pair in accepted:
        _union(parent, pair.representative, pair.absorbed)

    # 덩이별 구성원.
    groups: dict[str, list[str]] = {}
    for key in sorted(parent):
        groups.setdefault(_find(parent, key), []).append(key)

    # 크기 상한을 넘은 덩이는 통째로 버린다 — 별칭도 큐도 없다 (모듈 docstring).
    # 승격 보류보다 먼저다. 그 덩이의 쌍 수천 개가 큐로 가면 큐가 목록이 된다.
    oversized_roots = {root for root, members in groups.items() if len(members) > max_group_size}
    oversized = tuple(
        sorted(
            (_canonical(groups[root], df=df, promoted=()), len(groups[root]))
            for root in oversized_roots
        )
    )
    if oversized_roots:
        accepted = [
            pair for pair in accepted if _find(parent, pair.representative) not in oversized_roots
        ]
        for root in oversized_roots:
            groups.pop(root)

    # 승격된 것이 둘 이상인 덩이는 통째로 보류한다.
    held_roots = {
        root
        for root, members in groups.items()
        if sum(1 for member in members if member in promoted_set) >= 2
    }
    if held_roots:
        held: list[MergePair] = []
        kept: list[MergePair] = []
        for pair in accepted:
            (held if _find(parent, pair.representative) in held_roots else kept).append(pair)
        parked.extend(held)
        accepted = kept
        for root in held_roots:
            groups.pop(root, None)

    # 별칭마다 근거가 될 쌍 하나 — 그 별칭에 붙은 쌍 중 가장 강한 것.
    best: dict[str, MergePair] = {}
    for pair in accepted:
        for member in (pair.representative, pair.absorbed):
            current = best.get(member)
            if current is None or _evidence_order(pair) < _evidence_order(current):
                best[member] = pair

    aliases: list[Alias] = []
    merged_groups = 0
    for members in groups.values():
        canonical = _canonical(members, df=df, promoted=promoted_set)
        others = [member for member in members if member != canonical]
        if not others:
            continue
        merged_groups += 1
        for member in others:
            source = best[member]
            aliases.append(
                Alias(
                    domain=source.domain,
                    alias_key=member,
                    canonical_key=canonical,
                    layer=source.layer,
                    rule=source.rule,
                    confidence=source.confidence,
                    signal=source.signal,
                )
            )
    aliases.sort(key=lambda alias: (alias.domain, alias.alias_key))
    parked.sort(key=_pair_order)
    return AliasResolution(
        aliases=tuple(aliases),
        parked=tuple(parked),
        merged_groups=merged_groups,
        oversized=oversized,
    )


def _canonical(members: list[str], *, df: Mapping[str, int], promoted: Collection[str]) -> str:
    """대표 하나. 승격된 것이 있으면 그것, 없으면 DF 최대(동률은 사전순)."""
    already = sorted(member for member in members if member in promoted)
    if already:
        return already[0]
    return min(members, key=lambda member: (-df.get(member, 0), member))


def _pair_order(pair: MergePair) -> tuple:
    return (pair.domain, pair.representative, pair.absorbed, pair.layer, pair.rule)


def _evidence_order(pair: MergePair) -> tuple:
    """강한 근거가 먼저 오는 정렬 키. 층이 낮고 신뢰도가 높은 쪽이 강하다."""
    return (pair.layer, -pair.confidence, pair.rule, pair.representative, pair.absorbed)


def _find(parent: dict[str, str], key: str) -> str:
    parent.setdefault(key, key)
    root = key
    while parent[root] != root:
        root = parent[root]
    # 경로 압축. 덩이가 사슬로 길어져도 두 번째 조회부터 상수 시간이다.
    while parent[key] != root:
        parent[key], key = root, parent[key]
    return root


def _union(parent: dict[str, str], left: str, right: str) -> None:
    left_root, right_root = _find(parent, left), _find(parent, right)
    if left_root == right_root:
        return
    # 사전순으로 작은 쪽을 뿌리로 — 뿌리가 결정적이어야 덩이 목록이 실행마다 같다.
    # 대표 선정은 뿌리와 무관하게 `_canonical` 이 따로 한다.
    low, high = sorted((left_root, right_root))
    parent[high] = low
