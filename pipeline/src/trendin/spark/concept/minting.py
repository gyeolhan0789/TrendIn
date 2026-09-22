"""판정이 "새 개념" 이라고 한 표현 중 **무엇을 실제로 만들 것인가**.

**왜 판정만으로는 만들지 않나.** 이름 판정은 한 번 보고 답한다. 그 한 번이 틀리면 사전에
쓰레기가 남고, 사전은 순위를 접는 데 쓰이므로 그 여파가 화면까지 간다. 그래서 판정 위에
**기사가 스스로 증명한 것**을 얹는다 — 여러 기사에, 여러 매체에 거듭 나왔는가.

2026-09-22 운영 미등록 7,124개를 보니 기사 3건 이상이면서 매체 2곳 이상인 것이 2,590개였다.
매체가 한 곳뿐인 것이 679개(9.5%)라 이 조건이 걸러 내는 것은 주로 한 매체의 일회성 표기다.

**만든 개념은 세지 않는 것으로 둔다.** `countable=false` 면 순위 접기가 이미 걸러 내므로
(`metrics/concepts.build_grouping`) 잘못 만든 개념 하나가 화면을 흔들지 않는다. 사람이 훑고
`countable=true` 로 올리는 것이 승격이고, `status='RETIRED'` 가 거부다. 둘 다 이미 있는 칸이라
스키마를 건드리지 않는다.

**출처로 가려낸다.** `source='auto:llm'` 이라 검수 화면이 "세지 않는 일반어" 와 "아직 못 믿는
새 개념" 을 구분할 수 있다. 두 가지가 `countable=false` 한 칸에 섞이는 것을 이것이 푼다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from trendin.spark.concept.judge import UNCOUNTED, name_key, name_variants

AUTO_SOURCE = "auto:llm"


@dataclass(frozen=True, slots=True)
class Evidence:
    """그 표현이 기사에서 스스로 증명한 것."""

    articles: int
    sources: int


@dataclass(frozen=True, slots=True)
class MintPolicy:
    min_articles: int
    min_sources: int


@dataclass(frozen=True, slots=True)
class Mint:
    """새로 만들 개념 하나와 거기 붙일 표기."""

    canonical_name: str
    category: str
    lang: str
    surface: str
    normalized: str
    articles: int
    sources: int


def select(
    proposals: Sequence[tuple[str, str, str, str, str]],
    evidence: Mapping[str, Evidence],
    known_names: Iterable[str],
    policy: MintPolicy,
) -> tuple[Mint, ...]:
    """만들 것을 고른다. `proposals` 는 `(lang, normalized, surface, english_name, category)`.

    거르는 것은 넷이다 — 세지 않기로 한 분류, 이미 사전에 있는 이름, 근거가 모자란 표현,
    그리고 **한 회차 안의 중복**이다. `슈즈` 와 `신발` 이 같은 영어 이름으로 오면 개념을 둘
    만들 것이 아니다. 지금은 첫 번째만 만들고 나머지는 다음 회차에 사전 조회로 붙는다.
    """
    # 단복수 흔들림까지 본다 — `shoes` 가 있는데 `shoe` 로 개념을 또 만들면 안 된다.
    seen = {variant for name in known_names for variant in name_variants(name_key(name))}
    out: list[Mint] = []
    for lang, normalized, surface, english_name, category in proposals:
        if category in UNCOUNTED:
            continue
        key = name_key(english_name)
        if not key or any(variant in seen for variant in name_variants(key)):
            continue
        found = evidence.get(normalized)
        if found is None:
            continue
        if found.articles < policy.min_articles or found.sources < policy.min_sources:
            continue
        seen.update(name_variants(key))
        out.append(
            Mint(
                canonical_name=_display_name(english_name, surface),
                category=category,
                lang=lang,
                surface=surface or normalized,
                normalized=normalized,
                articles=found.articles,
                sources=found.sources,
            )
        )
    return tuple(out)


def _display_name(english_name: str, surface: str | None) -> str:
    """대표 이름의 대소문자. 표기가 같은 말이면 그쪽을 쓴다.

    모델이 `Zendaya` 를 어떤 회차에는 `zendaya` 로 돌려준다. `canonical_name` 은 화면에 보이는
    이름이라 `zendaya` 로 굳으면 보기 흉하고, 표에 UNIQUE 가 대소문자를 가리므로 나중에 같은
    사람이 둘로 갈릴 여지도 생긴다. 표기가 같은 말이면 기사에 쓰인 대로 적는다.
    """
    name = (english_name or "").strip()
    written = (surface or "").strip()
    if written and name_key(written) == name_key(name):
        return written
    return name
