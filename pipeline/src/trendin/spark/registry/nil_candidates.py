"""개념 테이블에 없는 표기끼리의 변형 후보 — 묶음째 LLM 에 물을 덩이를 만든다 (S15P21A102-386).

개념 연결은 새 표기를 **이미 있는** 개념에만 붙인다. 개념 테이블에 없던 이름이 여러 변형으로
한꺼번에 들어오면 서로 모르는 채로 순위 자리를 나눠 갖는다 — 2026-09-24 24H 1~4위가
`Vogue World` 계열 네 표기였다. 연도·시즌만 다른 것은 `registry/edition.py` 가 글자만 보고
접지만, `Vogue World` ↔ `Vogue World: Milano` 처럼 낱말이 더 붙은 관계는 뜻을 봐야 한다.

이 모듈은 **후보만** 낸다. 합치지 않는다 — 판정은 덩이째 LLM 이 한다. 그래서 정밀도보다
재현율을 본다. 놓친 쌍은 다시 볼 기회가 없고, 잘못 올린 쌍은 판정이 걸러 낸다.

| 규칙 | 예 | |
| --- | --- | --- |
| `contain` | `vogue world` ⊂ `vogue world milano` | 두 낱말 이상이 이어서 들어 있다 |
| `prefix` | `abito da sera` ~ `abito da sposa` | 앞 두 낱말이 같고 둘 다 세 낱말 이상 |
| `edition` | `met gala` ~ `2026 met gala` | 연도·시즌을 떼면 같다 (`edition_key`) |
| `acronym` | `lfw` ~ `london fashion week` | 머리글자가 같고 **같은 기사에 함께 나온다** |

**한 낱말만 겹치는 것은 후보가 아니다.** `vogue` ↔ `vogue world` 는 잡지와 행사다. 한 낱말은
대개 브랜드·도시·일반어라 붙는 말이 뜻을 바꾼다.

**2026-09-24 운영 실측** (30일 언급이 있는 키워드 8,412 개, 사람 검수 라벨 608 쌍) — 문자열
후보 608 쌍 중 순위에서 합칠 것(같은 대상 · 같은 시리즈의 다른 회차)은 23% 였다. 대부분은
`미니 드레스` ↔ `블랙 미니 드레스` 같은 수식어 변형이다. 등장 패턴(같은 기사 · 같은 날 급증 ·
첫 등장 차이)은 어느 것도 걸러 낼 만큼 갈리지 않았다 — 같은 기사 2건 이상이 정밀도 61%
재현율 27% 다. 그래서 패턴은 거르는 데 쓰지 않고 판정에 넘기는 근거로만 둔다.

**머리글자는 같은 기사를 조건으로 건다.** 머리글자만 보면 141 쌍 중 7 쌍만 맞았다 —
`dc` 는 `DC Comics` 도 `Doja Cat` 도 `dress code` 도 된다. 같은 기사에 함께 나오면
(`LFW` ↔ `London Fashion Week` 32 건) 거의 맞다. 라틴 문자만 본다 — 한국어 음절 머리글자는
`스키` ↔ `스트레이 키즈` 같은 우연을 낸다.

**앞 두 낱말이 같은 무리가 크면 형제 품목이다.** `gonna a matita` · `gonna a pieghe` ·
`gonna a ruota` … 는 모두 치마의 종류고 `t shirt …` 도 그렇다. 한 머리에 딸린 표기가
`PREFIX_GROUP_MAX` 를 넘으면 그 머리로는 후보를 만들지 않는다.

**흔한 머리말은 덩이를 잇지 않는다.** `fashion week` 은 도시마다 붙어서 이으면 파리·런던·밀라노
패션위크가 한 덩이가 된다. 후보가 `HUB_DEGREE` 보다 많은 표기는 쌍으로는 남기되 덩이를
잇지 않는다 — 그 쌍들은 따로 둘씩 묻는다.

**후보는 전체 키워드로 만들고 판정할 쌍은 나중에 추린다.** 형제 품목 무리의 크기와 흔한 머리말의
후보 수는 전체에서 세야 한다. 2026-09-25 에 24H 순위의 표기만 넣었더니 `fashion week` 이 흔해
보이지 않아 패션위크 12 표기가 한 덩이가 됐고 `fashion week de londres` ↔
`fashion week milanaise` 가 후보로 올라 한 줄이 됐다. 순서는 `candidate_pairs(전체)` →
순위 상위 쌍만 추림 →
`clusters(추린 쌍, degrees(전체 쌍))` 다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from trendin.spark.registry.edition import edition_base, edition_key

# 한 머리(앞 두 낱말)에 딸린 표기가 이보다 많으면 형제 품목으로 본다. 실측에서 딸린 표기가
# 넷~여섯인 머리의 쌍은 38 개 모두 다른 것이었다. 일곱인 `vogue world` 는 전부 합칠 쌍이지만
# 기준형 `vogue world` 가 `contain` 으로 모두 잇는다. 아홉인 `fashion week` 은 72 쌍 중 6 쌍만
# 맞았다 (`fashion week de paris` ↔ `fashion week parisienne` — 놓친다).
PREFIX_GROUP_MAX = 4
# 후보가 이보다 많은 표기는 덩이를 잇지 않는다. `vogue world` 가 회차·개최지 표기 일곱과
# 이어지므로 그보다는 커야 한다.
HUB_DEGREE = 8
# 덩이 하나에 담는 표기 수의 상한. 넘으면 판정에 넘기지 않고 둘씩 나눠 묻는다. 2026-09-25 운영
# 순위로 돌려 보니 패션위크 12 표기 덩이에서 모델이 `Fashion Week` ↔ `London Fashion Week` 를
# `same` 이라 했다 — 둘만 물으면 `narrower` 라 답하는 쌍이다. `vogue world` 계열 9 표기는 한 덩이로
# 잘 판정되므로 9 에 둔다.
MAX_CLUSTER = 9


@dataclass(frozen=True)
class Term:
    """후보를 찾을 표기 하나. `key` 는 `extract/keys.normalized_key` 를 거친 비교키다."""

    key: str
    docs: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, order=True)
class Pair:
    """후보 한 쌍. `a < b` 로 둔다 — 같은 쌍이 두 번 나오지 않게."""

    a: str
    b: str
    rules: tuple[str, ...]
    shared_docs: int


def _contains(short: list[str], long: list[str]) -> bool:
    n = len(short)
    return any(long[i : i + n] == short for i in range(len(long) - n + 1))


def _is_latin_word(token: str) -> bool:
    return token.isascii() and token.isalpha()


def _initials(tokens: list[str]) -> str | None:
    if len(tokens) < 2 or not all(_is_latin_word(token) for token in tokens):
        return None
    return "".join(token[0] for token in tokens)


def _rules(a: list[str], b: list[str], key_a: str, key_b: str) -> list[str]:
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    rules: list[str] = []
    if 2 <= len(short) < len(long) and _contains(short, long):
        rules.append("contain")
    elif len(short) >= 3 and short[:2] == long[:2]:
        rules.append("prefix")
    if edition_key(key_a) == edition_key(key_b) and (edition_base(key_a) or edition_base(key_b)):
        rules.append("edition")
    return rules


def candidate_pairs(terms: Iterable[Term]) -> list[Pair]:
    """표기 목록 → 후보 쌍. 모든 쌍을 비교하지 않고 이어진 두 낱말·머리글자로 색인해 찾는다."""
    by_key = {term.key: term for term in terms}
    tokens = {key: key.split() for key in by_key}

    by_bigram: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_edition: dict[str, set[str]] = defaultdict(set)
    by_initials: dict[str, set[str]] = defaultdict(set)
    prefix_group: dict[tuple[str, str], int] = defaultdict(int)
    for key, toks in tokens.items():
        for i in range(len(toks) - 1):
            by_bigram[(toks[i], toks[i + 1])].add(key)
        by_edition[edition_key(key)].add(key)
        initials = _initials(toks)
        if initials:
            by_initials[initials].add(key)
        if len(toks) >= 3:
            prefix_group[(toks[0], toks[1])] += 1

    found: dict[tuple[str, str], list[str]] = {}
    for key, toks in tokens.items():
        near = set(by_edition[edition_key(key)])
        for i in range(len(toks) - 1):
            near |= by_bigram[(toks[i], toks[i + 1])]
        for other in near:
            if other <= key:
                continue
            rules = _rules(toks, tokens[other], key, other)
            if "prefix" in rules and prefix_group[(toks[0], toks[1])] > PREFIX_GROUP_MAX:
                rules.remove("prefix")
            if rules:
                found[(key, other)] = rules
        if len(toks) == 1 and _is_latin_word(key) and 2 <= len(key) <= 5:
            for other in by_initials.get(key, ()):
                pair = (key, other) if key < other else (other, key)
                if by_key[key].docs & by_key[other].docs:
                    found.setdefault(pair, []).append("acronym")

    return sorted(
        Pair(a, b, tuple(rules), len(by_key[a].docs & by_key[b].docs))
        for (a, b), rules in found.items()
    )


def degrees(pairs: Iterable[Pair]) -> dict[str, int]:
    """표기마다 후보 쌍의 수. 흔한 머리말을 가르는 데 쓴다."""
    degree: dict[str, int] = defaultdict(int)
    for pair in pairs:
        degree[pair.a] += 1
        degree[pair.b] += 1
    return dict(degree)


def clusters(
    pairs: Iterable[Pair], degree: Mapping[str, int] | None = None
) -> list[tuple[str, ...]]:
    """후보 쌍 → 판정에 넘길 덩이. 흔한 머리말과 너무 큰 덩이는 둘씩 나눈다.

    연결 요소로 모으되 후보가 `HUB_DEGREE` 를 넘는 표기는 잇는 데 쓰지 않는다. 그 표기의 쌍과
    `MAX_CLUSTER` 를 넘는 덩이의 쌍은 두 표기짜리 덩이로 따로 낸다.

    **흔한 머리말은 전체 표기로 센다** (`degree` — 모든 키워드의 후보 쌍으로 만든 `degrees`). 판정할
    쌍만 추려서 세면 흔한 말이 흔해 보이지 않는다 — 2026-09-25 24H 순위만으로 세니 `fashion week`
    의 후보가 여덟이 안 돼서 패션위크 12 표기가 한 덩이로 묶였다. 주지 않으면 받은 쌍으로 센다.
    """
    pairs = list(pairs)
    degree = degree if degree is not None else degrees(pairs)

    parent: dict[str, str] = {}

    def find(key: str) -> str:
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    linked: list[Pair] = []
    loose: list[Pair] = []
    for pair in pairs:
        if degree.get(pair.a, 0) > HUB_DEGREE or degree.get(pair.b, 0) > HUB_DEGREE:
            loose.append(pair)
        else:
            linked.append(pair)
            parent[find(pair.a)] = find(pair.b)

    groups: dict[str, set[str]] = defaultdict(set)
    for pair in linked:
        groups[find(pair.a)] |= {pair.a, pair.b}
    out: list[tuple[str, ...]] = []
    for members in groups.values():
        if len(members) <= MAX_CLUSTER:
            out.append(tuple(sorted(members)))
    too_big = {key for members in groups.values() if len(members) > MAX_CLUSTER for key in members}
    loose += [pair for pair in linked if pair.a in too_big]
    out += [(pair.a, pair.b) for pair in loose]
    return sorted(out)
