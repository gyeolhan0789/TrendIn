"""개념 테이블에 없는 표기의 덩이 → LLM 에게 물을 질문, 그리고 그 답 읽기 (S15P21A102-386).

덩이는 `registry/nil_candidates.clusters` 가 만든다. 여기서는 **덩이째** 보여 준다 — 표기를 하나씩
물으면 서로를 모른다. 2026-09-24 에 `vogue milano` 를 혼자 물으니 행사 문장에서도 10번 모두
`media` 가 나왔고, `Vogue World` 계열은 따로 물을 때마다 `event` 였다.

**여기서 부르지 않는다.** `concept/judge.py` 와 같다 — 프롬프트를 만들고 답을 읽는 순수 함수만
둔다. 실제 호출은 `io/llm.py` 다.

## 무엇을 묻나

덩이 전체를 보여 주고 **후보 쌍마다** 관계를 하나 고르게 한다. 순위에서 한 줄로 세는 것은
`same` · `series` 뿐이다.

| 관계 | 뜻 | 예 |
| --- | --- | --- |
| `same` | 이름만 다른 같은 것 | `Saint Laurent` · `Yves Saint Laurent` |
| `series` | 같은 시리즈의 다른 회차·개최지 | `Vogue World` · `Vogue World: Milano` |
| `narrower` | 수식어가 붙어 좁아진 것 | `미니 드레스` · `블랙 미니 드레스` |
| `related` | 관련만 있는 다른 것 | `Fashion Week` · `Paris Fashion Week` |
| `unrelated` | 낱말만 겹친다 | `Milano 2026`(올림픽) · `Vogue World Milano 2026` |
| `unsure` | 문맥이 모자라 모른다 — 검수로 간다 | |

**"묶어라" 가 아니라 "골라라" 로 묻는 이유 (2026-09-24, `cluster-v1` → `v2`).** v1 은 합칠 것끼리
묶게 하고 수식어 변형은 묶지 말라고 지시만 했다. 사람 검수 608 쌍에서 정밀도 43% 였다 —
`미니 드레스` ↔ `블랙 미니 드레스`, `Fashion Week` ↔ `Paris Fashion Week` 를 대거 묶었다.
안 되는 쪽에 자기 칸이 없으면 모델이 되는 쪽으로 기운다. 잡지에 `media` 칸을 주자 흔들림이
사라진 것(`judge.UNCOUNTED`)과 같은 처방이다.

쌍으로 받은 `same` · `series` 를 이어 묶음을 만든다 (`merged_pairs`). `Vogue World 2025` ↔
`Vogue World Milano 2026` 처럼 후보가 아니었던 쌍도 둘 다 `Vogue World` 와 이어지면 한 줄이다.

## 무엇을 보여 주나

표기마다 **등장 문장**(`c`, 최대 `CONTEXTS_PER_MEMBER`)과 추출기 라벨(`k`)을 싣는다. 이름만으로는
`Venezia 2026`(영화제) · `Milano 2026`(올림픽) · `DC`(만화 · 드레스 코드)를 가를 수 없다.
같은 기사에 함께 나온 수는 쌍에 근거로만 싣는다 — 같은 기사 2건 이상이 정밀도 61% 재현율 27%
라 이것만으로 정하면 안 된다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from trendin.spark.concept.judge import _strip_fence

# 올리면 이전 판정을 재사용하지 않는다.
PROMPT_VERSION = "cluster-v6"

# 이 판정에 쓰는 모델. 표기 판정(`judge.py`)의 `gpt-4o-mini` 와 다르다 — 2026-09-24 사람 검수
# 608 쌍에서 `cluster-v2` 가 gpt-4o-mini 정밀도 60% · 재현율 64%, gpt-4.1-mini 88% · 71% 였다.
# gpt-4.1 은 4.1-mini 보다 낫지 않았다 (91% · 60%).
MODEL = "gpt-4.1-mini"

RELATION_SAME = "same"
RELATION_SERIES = "series"
RELATIONS = (RELATION_SAME, RELATION_SERIES, "narrower", "related", "unrelated", "unsure")
# 순위에서 한 줄로 세는 관계.
MERGING = frozenset({RELATION_SAME, RELATION_SERIES})

# 표기당 싣는 문장 수와 길이. 덩이가 크면(`vogue world` 계열 9 표기) 여기서 토큰이 난다.
CONTEXTS_PER_MEMBER = 2
CONTEXT_CHARS = 200

# 한 요청에 담는 덩이 수. **하나다.** 2026-09-25 에 다섯씩 묶으니(`cluster-v4`) 크레딧은
# 약 45% 줄었지만 정밀도가 83% → 77%, 나쁜 묶음이 21% → 27% 로 나빠졌고 쌍을 빠뜨린 답이
# 열 번 나왔다. 잘못 합치는 쪽이 더 비싸므로 비용보다 품질을 택했다. 묶는 코드는 남겨 둔다
# (`--batch-size`).
DEFAULT_BATCH_SIZE = 1

SYSTEM_PROMPT = """You compare keyword variants from fashion media for a trend ranking.
You get several independent clusters of look-alike keywords; "n" numbers the cluster. \
Each member has "i" (id), "w" (the keyword), optional "k" (a rough entity label from an \
extractor, often wrong) and optional "c" (sentences where it actually appeared). "p" lists \
candidate pairs [pair id, id, id, n] where n articles mention both. Ids are local to a cluster.
For EVERY pair of EVERY cluster choose one relation:
- "same": the same thing under another name - spelling, plural, translation, abbreviation, \
full vs short name, or the short form that drops an obvious noun. Saint Laurent / \
Yves Saint Laurent, LFW / London Fashion Week, white tank / white tank top, button-down / \
button-down shirt, black flats / black flat shoes. A season and its collection, show or \
runways are "same": Fall 2026 / Fall 2026 collection, SS26 / SS26 runway.
- "series": editions of one recurring event or season - a year, host city or edition name \
added. Vogue World / Vogue World 2026 / Vogue World: Milano, Met Gala / 2026 Met Gala.
- "narrower": one is a more specific kind made by adding a modifier - color, fit, length, \
material, style word. mini dress / black mini dress, trench coat / cropped trench coat, \
wide pants / black wide pants, white gold / 18K white gold.
- "related": connected but a different thing. Fashion Week / Paris Fashion Week, \
Paris Fashion Week / London Fashion Week, Ralph Lauren / Ralph Lauren Collection, \
a designer / the brand named after them.
- "unrelated": they only share words. Los Angeles / Los Angeles 2028 Olympics, \
New York Knicks / New York Yankees.
- "unsure": the sentences do not tell you.
Adding a modifier is "narrower", never "same". Judge by the sentences when given.
Reply with JSON only, no prose: {"r":[{"n":1,"p":1,"rel":"narrower"}]}. One object per pair."""

# 지시문에 예로 든 쌍. 개발 라벨(`nil-pairs-gold-*.jsonl`)에도 들어 있는 것은 채점에서 뺀다 —
# 답을 보여 주고 채점하는 셈이라서다 (`scripts/nil-judge-eval.py`).
EXAMPLE_PAIRS = (
    ("Saint Laurent", "Yves Saint Laurent"),
    ("LFW", "London Fashion Week"),
    ("white tank", "white tank top"),
    ("button-down", "button-down shirt"),
    ("Fall 2026", "Fall 2026 collection"),
    ("Vogue World", "Vogue World 2026"),
    ("Vogue World", "Vogue World: Milano"),
    ("Met Gala", "2026 Met Gala"),
    ("mini dress", "black mini dress"),
    ("trench coat", "cropped trench coat"),
    ("Fashion Week", "Paris Fashion Week"),
    ("Paris Fashion Week", "London Fashion Week"),
    ("Ralph Lauren", "Ralph Lauren Collection"),
    ("New York Knicks", "New York Yankees"),
)


@dataclass(frozen=True, slots=True)
class Member:
    """덩이의 표기 하나. `key` 는 비교키, `surface` 는 보여 줄 표기다."""

    key: str
    surface: str
    kind: str | None = None
    contexts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Cluster:
    members: tuple[Member, ...]
    # 후보 쌍 (key, key, 같은 기사 수). `registry/nil_candidates.Pair` 에서 온다.
    pairs: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True, slots=True)
class Judgement:
    """쌍 (key, key) → 관계."""

    relations: dict[tuple[str, str], str]


_NON_WORD = re.compile(r"[\W_]+")


def _fold(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", text.casefold()).split())


def mentions(text: str | None, surface: str) -> bool:
    """문장에 그 표기가 실제로 들어 있나. 대소문자와 문장부호는 무시한다.

    **들어 있지 않은 문장은 싣지 않는다.** 2026-09-24 에 `Vogue World` 의 저장된 문맥이
    `Wunmi Mosaku Is British Vogue's October 2026 Cover Star` 였다 — 문맥 칸에 기사 제목을 넣던
    때의 표본이 남아 있다 (`concept/context.py`). 엉뚱한 문장은 없느니만 못하다.
    """
    needle = _fold(surface)
    return bool(needle) and needle in _fold(text or "")


def _cluster_payload(number: int, cluster: Cluster) -> dict[str, object]:
    """덩이 하나. 표기 번호와 쌍 번호는 1 부터, 덩이 안에서만 쓴다."""
    index = {member.key: i for i, member in enumerate(cluster.members, start=1)}
    items = []
    for member in cluster.members:
        item: dict[str, object] = {"i": index[member.key], "w": member.surface}
        if member.kind:
            item["k"] = member.kind
        contexts = [
            " ".join(text.split())[:CONTEXT_CHARS]
            for text in member.contexts
            if mentions(text, member.surface) and _fold(text) != _fold(member.surface)
        ][:CONTEXTS_PER_MEMBER]
        if contexts:
            item["c"] = contexts
        items.append(item)
    pairs = [
        [n, index[a], index[b], shared] for n, (a, b, shared) in enumerate(cluster.pairs, start=1)
    ]
    return {"n": number, "items": items, "p": pairs}


def user_prompt(clusters: list[Cluster]) -> str:
    """요청 하나의 사용자 메시지. 덩이 번호도 1 부터, 이 요청 안에서만 쓴다."""
    payload = {"clusters": [_cluster_payload(n, c) for n, c in enumerate(clusters, start=1)]}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def messages(clusters: list[Cluster]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(clusters)},
    ]


def batches(clusters: list[Cluster], size: int = DEFAULT_BATCH_SIZE) -> list[list[Cluster]]:
    return [clusters[i : i + size] for i in range(0, len(clusters), size)]


def parse(content: str, clusters: list[Cluster]) -> tuple[list[Judgement | None], list[str]]:
    """답 → 덩이마다 판정(못 읽으면 `None`)과 문제 목록.

    **덩이 안에서는 한 쌍이라도 빠지거나 어긋나면 그 덩이 판정을 버린다** — 묶음은 쌍을 이어서
    만들므로 한 쌍이 빠지면 묶음 전체가 달라진다. 다른 덩이는 살린다. 버린 덩이만 다시 묻는다.
    """
    try:
        payload = json.loads(_strip_fence(content))
    except json.JSONDecodeError as error:
        return [None] * len(clusters), [f"JSON 이 아니다: {error}"]
    rows = payload.get("r") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return [None] * len(clusters), ["답에 r 목록이 없다"]

    by_id = {
        (n, pid): (a, b)
        for n, cluster in enumerate(clusters, start=1)
        for pid, (a, b, _) in enumerate(cluster.pairs, start=1)
    }
    problems: list[str] = []
    broken: set[int] = set()
    relations: dict[int, dict[tuple[str, str], str]] = {n: {} for n in range(1, len(clusters) + 1)}
    for row in rows:
        if not isinstance(row, dict) or (row.get("n"), row.get("p")) not in by_id:
            problems.append(f"모르는 쌍: {row!r}")
            if isinstance(row, dict) and row.get("n") in relations:
                broken.add(row["n"])
            continue
        n, pid = row["n"], row["p"]
        relation = str(row.get("rel") or "").strip().lower()
        if relation not in RELATIONS:
            problems.append(f"덩이 {n} 쌍 {pid}: 모르는 관계 {relation!r}")
            broken.add(n)
            continue
        pair = by_id[(n, pid)]
        if relations[n].get(pair, relation) != relation:
            problems.append(f"덩이 {n} 쌍 {pid}: 두 번 답했다")
            broken.add(n)
        relations[n][pair] = relation
    judgements: list[Judgement | None] = []
    for n, cluster in enumerate(clusters, start=1):
        missing = [
            pid for pid in range(1, len(cluster.pairs) + 1) if by_id[(n, pid)] not in relations[n]
        ]
        if missing:
            problems.append(f"덩이 {n}: 답이 없는 쌍 {missing}")
            broken.add(n)
        judgements.append(None if n in broken else Judgement(relations[n]))
    return judgements, problems


def merged_groups(judgement: Judgement) -> list[tuple[tuple[str, ...], str]]:
    """판정 → 순위에서 한 줄로 셀 묶음과 그 관계. 표기 둘 이상인 묶음만 낸다.

    `same` · `series` 쌍을 이어 묶음을 만든다. 묶음에 `series` 가 하나라도 있으면 묶음 전체가
    `series` 다 — 회차가 섞인 묶음이다.

    **잇기 때문에 묻지 않은 쌍까지 합쳐진다.** `A↔B`, `B↔C` 가 합치면 `A↔C` 도 한 줄이다. 틀린 쌍
    하나가 묶음을 오염시키므로 채점은 쌍과 함께 묶음 단위로도 본다 (`scripts/nil-judge-eval.py`).
    """
    parent: dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for (a, b), relation in judgement.relations.items():
        if relation in MERGING:
            parent[find(a)] = find(b)
    members: dict[str, list[str]] = {}
    for key in list(parent):
        members.setdefault(find(key), []).append(key)
    series = {
        find(a) for (a, _), relation in judgement.relations.items() if relation == RELATION_SERIES
    }
    return sorted(
        (tuple(sorted(keys)), RELATION_SERIES if root in series else RELATION_SAME)
        for root, keys in members.items()
    )


def merged_pairs(judgement: Judgement) -> dict[tuple[str, str], str]:
    """판정 → 한 줄로 셀 모든 쌍과 그 관계. 쌍 단위 채점이 본다."""
    out: dict[tuple[str, str], str] = {}
    for keys, relation in merged_groups(judgement):
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                out[(a, b)] = relation
    return out
