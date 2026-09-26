"""미등록 표기를 덩이째 판정해 **기존 개념에 잇는다** (S15P21A102-394).

`registry/nil_candidates` 가 후보 덩이를, `concept/cluster_judge` 가 덩이째 판정을 만든다
(S15P21A102-386). 여기서는 그 둘을 개념 Job 에 붙인다 — 창 안 기사에서 표기마다 등장 기사를
모으고, 미등록 표기가 든 덩이를 고르고, 판정이 `same` · `series` 로 이은 묶음에 **기존 개념이
딱 하나** 있으면 나머지 미등록 표기를 그 개념의 표현으로 잇는다.

**왜 순위(aggregate)가 아니라 개념 테이블인가.** 386 브랜치에서 판정 파일을 aggregate 가 읽어
순위에서만 접어 보았다. 그러려면 판정 저장 표 · 판정을 돌릴 자리 · aggregate 안의 LLM 호출이
따로 있어야 한다. 표현으로 넣으면 aggregate 의 개념 접기(`metrics/concepts.build_grouping`)가
그대로 합치고, 되돌리기는 자동 연결과 같은 원장(`pl_concept_change`)을 쓴다.

**개념이 없는 묶음은 건너뛴다.** `White Lotus` ↔ `The White Lotus` 처럼 둘 다 미등록이면 새
개념을 만들어야 하는데, 분류(category)를 정할 근거가 판정에 없다. 개념이 둘 이상 걸린 묶음도
건너뛴다 — 판정이 두 개념을 하나라고 했다는 뜻이라 사람이 볼 일이다.

**묻는 덩이를 줄인다.** 잇기에 쓸 수 있는 덩이만 묻는다 — 기존 개념 표기가 하나 이상, 기사
문턱을 넘는 미등록 표기가 하나 이상. 운영 30일 창에서 덩이는 수백 개지만 잇기에 쓸 수 있는 것은
그중 일부다. 한 번 판정한 덩이는 구성원과 쌍이 같으면 다시 묻지 않는다 (`cache_key`).

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from trendin.spark.concept.cluster_judge import (
    CONTEXTS_PER_MEMBER,
    Cluster,
    Judgement,
    Member,
    mentions,
    merged_groups,
    messages,
    parse,
)
from trendin.spark.concept.dictionary import Dictionary
from trendin.spark.concept.mapping import Keyword
from trendin.spark.concept.normalize import concept_key, lang_of_surface
from trendin.spark.registry.nil_candidates import (
    HUB_DEGREE,
    Term,
    candidate_pairs,
    clusters,
    degrees,
)

# 판정 캐시(`pl_concept_judgement_cache`)의 `lang` 칸. 표기 하나가 아니라 덩이 하나의 판정이라
# 표기 판정과 열쇠가 겹치지 않게 한다.
CACHE_LANG = "cluster"

# 표기당 모아 두는 문장 수. 판정에 싣는 것은 `CONTEXTS_PER_MEMBER` 까지고, 표기가 실제로 든
# 문장만 싣는다 (`cluster_judge.mentions`) — 그래서 넉넉히 모은다.
CONTEXT_POOL = 10


@dataclass(slots=True)
class Observed:
    """창 안에서 본 표기 하나. `concept_id` 는 사전에서 개념이 하나로 정해질 때만 있다."""

    lang: str
    key: str
    surface: str
    concept_id: int | None
    ambiguous: bool = False
    docs: set[int] = field(default_factory=set)
    contexts: list[str] = field(default_factory=list)
    # 흔한 머리말이다 — 후보가 `HUB_DEGREE` 보다 많다 (`select_clusters` 가 단다).
    hub: bool = False

    @property
    def unmapped(self) -> bool:
        return self.concept_id is None and not self.ambiguous

    @property
    def linkable(self) -> bool:
        """개념에 이을 수 있는 미등록 표기. **흔한 머리말은 잇지 않는다.**

        `fashion week` 은 도시마다 붙는다. 2026-09-25 운영 덤프에서 판정이 `Fashion Week` 을
        `Paris Fashion Week` · `Milano Fashion Week` 과 둘씩 따로 물을 때 `same` 이라 한 쌍이 있었다
        — 두 개념이 부딪혀 막혔지만(`plan_all`) 한 도시와만 그랬으면 일반명사가 그 도시에 합쳐진다.
        """
        return self.unmapped and not self.hub


@dataclass(frozen=True, slots=True)
class PlannedLink:
    """판정이 이은 미등록 표기 하나와 그것을 붙일 개념."""

    lang: str
    normalized: str
    surface: str
    concept_id: int
    relation: str
    group: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Policy:
    enabled: bool = False
    # 판정을 사전에 넣을지. 끄면 판정만 하고 이을 것을 로그로 남긴다 — 자동 연결의 `apply_links`
    # 와 같은 잠금이다.
    apply: bool = False
    # 한 회차에 LLM 에 묻는 덩이 수의 상한. 다시 물은 것도 센다.
    max_calls: int = 60

    @classmethod
    def from_mapping(cls, section: Mapping[str, object]) -> "Policy":
        policy = cls(
            enabled=bool(section.get("enabled", False)),
            apply=bool(section.get("apply", False)),
            max_calls=int(section.get("max_calls", 60)),  # type: ignore[arg-type]
        )
        if policy.max_calls < 1:
            raise ValueError("concept.nil_grouping.max_calls 는 1 이상이어야 한다")
        return policy


def observe(
    grouped: Mapping[int, Sequence[Keyword]],
    dictionary: Dictionary,
    sentences: Mapping[tuple[str, str], Iterable[str]] | None = None,
) -> dict[str, Observed]:
    """기사별 키워드 → 비교키마다 등장 기사 · 문장 · 개념.

    `sentences` 는 미등록 표기가 실제로 나온 문장이다 (`concept/context.py` 가 본문에서 찾은 것).
    키워드의 `context` 는 기사 제목이 섞여 있어 뒤에 붙인다.

    **비교키 하나에 언어가 둘이면 먼저 본 쪽을 쓴다.** 비교키가 문자 체계를 따라가므로(한글 ·
    라틴) 실제로 겹치지 않는다.
    """
    out: dict[str, Observed] = {}
    for article_id, keywords in grouped.items():
        for keyword in keywords:
            key = concept_key(keyword.surface)
            if not key:
                continue
            item = out.get(key)
            if item is None:
                lang = lang_of_surface(keyword.surface, None)
                hits = dictionary.lookup(lang, key)
                concepts = {hit.concept.concept_id for hit in hits}
                item = out[key] = Observed(
                    lang=lang,
                    key=key,
                    surface=keyword.surface,
                    concept_id=next(iter(concepts)) if len(concepts) == 1 else None,
                    ambiguous=len(concepts) > 1,
                )
            item.docs.add(article_id)
            if keyword.context and len(item.contexts) < CONTEXT_POOL:
                item.contexts.append(keyword.context)
    for (lang, key), texts in (sentences or {}).items():
        item = out.get(key)
        if item is None or item.lang != lang:
            continue
        found = [text for text in texts if text]
        item.contexts = (found + item.contexts)[:CONTEXT_POOL]
    return out


def select_clusters(observed: Mapping[str, Observed], *, min_articles: int) -> list[Cluster]:
    """잇기에 쓸 수 있는 덩이만 고른다.

    후보 쌍은 **창 안의 모든 표기로** 만든다 — 흔한 머리말(`fashion week`)과 형제 품목 무리는
    전체에서 세야 한다 (`registry/nil_candidates` 머리말). 그중 한쪽이 기사 문턱을 넘는 미등록
    표기인 쌍만 남기고, 덩이에 기존 개념 표기가 하나도 없으면 묻지 않는다.
    """
    terms = [Term(key, frozenset(str(doc) for doc in item.docs)) for key, item in observed.items()]
    everything = candidate_pairs(terms)
    degree = degrees(everything)
    for key, count in degree.items():
        observed[key].hub = count > HUB_DEGREE

    def eligible(key: str) -> bool:
        item = observed[key]
        return item.linkable and len(item.docs) >= min_articles

    chosen = [pair for pair in everything if eligible(pair.a) or eligible(pair.b)]
    shared = {(pair.a, pair.b): pair.shared_docs for pair in chosen}
    out: list[Cluster] = []
    for keys in clusters(chosen, degree):
        if not any(observed[key].concept_id is not None for key in keys):
            continue
        members = tuple(
            Member(key, observed[key].surface, None, _contexts(observed[key])) for key in keys
        )
        pairs = tuple(
            (a, b, shared[(a, b)])
            for i, a in enumerate(keys)
            for b in keys[i + 1 :]
            if (a, b) in shared
        )
        out.append(Cluster(members, pairs))
    return out


def _contexts(item: Observed) -> tuple[str, ...]:
    """표기가 실제로 든 문장을 앞에 둔다. 판정이 앞에서부터 `CONTEXTS_PER_MEMBER` 개만 싣는다."""
    found = [text for text in item.contexts if mentions(text, item.surface)]
    return tuple(dict.fromkeys(found))[: CONTEXTS_PER_MEMBER * 2]


def cache_key(cluster: Cluster) -> tuple[str, str]:
    """판정 캐시의 `(normalized, candidate_hash)`. 구성원과 쌍이 같으면 같은 판정을 쓴다.

    **문장은 열쇠에 넣지 않는다.** 넣으면 90분마다 도는 개념 Job 이 새 기사가 들 때마다 같은
    덩이를 다시 묻는다. 문맥이 바뀐 덩이를 다시 볼 장치는 따로 둔다 (티켓 범위 밖).
    """
    keys = sorted(member.key for member in cluster.members)
    pairs = sorted([a, b] for a, b, _ in cluster.pairs)
    digest = hashlib.sha256(
        json.dumps({"members": keys, "pairs": pairs}, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return keys[0], digest


class ChatClient(Protocol):
    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 1200) -> str: ...


# 쌍 하나의 답 출력 토큰 어림의 두 배 (`scripts/nil-judge-eval.py` 와 같다).
TOKENS_PER_PAIR = 32
# 어긋난 답이면 한 번 더 묻는다. 그래도 어긋나면 그 덩이는 이번 회차에 판정하지 않는다.
ATTEMPTS = 2


def ask(client: ChatClient, cluster: Cluster) -> tuple[Judgement | None, list[str], int]:
    """덩이 하나를 묻는다. 판정(못 읽으면 `None`) · 문제 목록 · 부른 횟수."""
    problems: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        content = client.chat(
            messages([cluster]), max_tokens=100 + TOKENS_PER_PAIR * len(cluster.pairs)
        )
        (judgement,), found = parse(content, [cluster])
        problems += found
        if judgement is not None:
            return judgement, problems, attempt
    return None, problems, ATTEMPTS


def to_payload(judgement: Judgement) -> dict[str, object]:
    return {"relations": sorted([a, b, r] for (a, b), r in judgement.relations.items())}


def from_payload(payload: Mapping[str, object] | None) -> Judgement | None:
    rows = (payload or {}).get("relations")
    if not isinstance(rows, list) or not rows:
        return None
    return Judgement({(str(a), str(b)): str(r) for a, b, r in rows})


def plan_links(
    judgement: Judgement, observed: Mapping[str, Observed]
) -> tuple[list[PlannedLink], list[tuple[tuple[str, ...], str]]]:
    """판정 → 이을 표기와 건너뛴 묶음(이유와 함께).

    묶음(`merged_groups`)마다 걸린 기존 개념을 센다. 하나면 묶음의 미등록 표기를 그 개념에 잇는다.
    사전에서 모호한 표기(개념 둘 이상)가 끼면 묶음째 건너뛴다 — 어느 개념의 묶음인지 모른다.
    """
    links: list[PlannedLink] = []
    skipped: list[tuple[tuple[str, ...], str]] = []
    for keys, relation in merged_groups(judgement):
        items = [observed[key] for key in keys if key in observed]
        if any(item.ambiguous for item in items):
            skipped.append((keys, "AMBIGUOUS"))
            continue
        concepts = {item.concept_id for item in items if item.concept_id is not None}
        if not concepts:
            skipped.append((keys, "NO_CONCEPT"))
            continue
        if len(concepts) > 1:
            skipped.append((keys, "MANY_CONCEPTS"))
            continue
        (concept_id,) = concepts
        links += [
            PlannedLink(item.lang, item.key, item.surface, concept_id, relation, keys)
            for item in items
            if item.linkable
        ]
    return links, skipped


def plan_all(
    judgements: Iterable[Judgement], observed: Mapping[str, Observed]
) -> tuple[list[PlannedLink], list[tuple[tuple[str, ...], str]]]:
    """여러 덩이의 판정 → 이을 표기. **두 덩이가 한 표기를 서로 다른 개념에 이으면 잇지 않는다.**

    흔한 머리말은 둘씩 따로 묻으므로(`nil_candidates.clusters`) 한 표기가 여러 덩이에 든다.
    """
    planned: list[PlannedLink] = []
    skipped: list[tuple[tuple[str, ...], str]] = []
    for judgement in judgements:
        links, passed = plan_links(judgement, observed)
        planned += links
        skipped += passed
    targets: dict[tuple[str, str], set[int]] = {}
    for link in planned:
        targets.setdefault((link.lang, link.normalized), set()).add(link.concept_id)
    out: dict[tuple[str, str], PlannedLink] = {}
    for link in planned:
        key = (link.lang, link.normalized)
        if len(targets[key]) > 1:
            skipped.append(((link.normalized,), "CONFLICT"))
            targets[key] = set()  # 한 번만 적는다
            continue
        if targets[key]:
            out.setdefault(key, link)
    return list(out.values()), skipped
