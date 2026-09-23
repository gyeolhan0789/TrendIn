"""미등록 표기의 문맥 — 그 낱말이 실제로 나온 문장을 고른다.

**왜 제목으로는 안 되나.** 지금까지 문맥 칸에는 기사 제목이 들어갔다 (`io/concepts.occurrences`).
2026-09-22 운영 미등록 6,936건을 보니 **제목에 그 낱말이 들어 있는 것은 9%뿐**이었다. 나머지
91%는 `ken` 의 문맥이 `Famous Guys Are Going Blonde` 인 식이라, 가릴 근거가 되기는커녕 엉뚱한
쪽으로 끌고 간다.

같은 날 실제 기사 제목으로 뜻 구분을 재 보니 여섯 쌍 전부 같은 답이 나왔다 — 프로그래밍 기사의
`coach` 와 Tapestry 실적 기사의 `Coach` 가 똑같이 패션 브랜드로 이어졌다.

**어느 문장을 고르나.** 문서 안에서 한 번만 나오는 것이 72.5% 라 대개 고를 것이 없다. 여러 번
나오면 **첫 등장**을 쓴다 — 기사 관행상 첫 언급이 가장 풀어서 쓰고(소속·정체를 붙이고), 뒤로
갈수록 짧아지거나 대명사로 바뀐다. 제목에 있으면 제목을 쓴다: 편집자가 직접 고른 요약이다.

**하나만 고르는 것이 최선은 아니다.** 표현 하나에 문맥 표본을 여럿 둘 수 있게 되어 있으므로
(`concept.unmapped.context_samples`), 기사마다 이 함수를 돌려 모으면 여러 문장이 쌓인다. 서로
다른 방향을 가리키면 그것 자체가 애매하다는 신호다.

**pyspark 를 import 하지 않는다** (층 1).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

# 문장 경계. 마침표·물음표·느낌표와 동아시아 문장부호를 함께 본다. 약어의 마침표까지 가려내지는
# 않는다 — 여기서 필요한 것은 그 낱말 둘레의 한 문장이지 완벽한 분할이 아니다.
_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|\n+")

# 너무 긴 문장은 잘라 넘긴다. 프롬프트에 그대로 실리는 값이라 상한이 있어야 한다.
MAX_CONTEXT_CHARS = 300


def sentences(body: str) -> list[str]:
    """본문을 문장으로 나눈다. 빈 조각은 버린다."""
    return [piece.strip() for piece in _BOUNDARY.split(body or "") if piece.strip()]


def find_sentence(body: str | None, title: str | None, surface: str) -> str | None:
    """그 표기가 나온 문장 하나. 없으면 `None`.

    제목에 있으면 제목을, 없으면 본문에서 **첫 등장** 문장을 돌려준다. 어느 쪽에도 없으면
    비운다 — 엉뚱한 제목을 문맥이라고 넘기느니 없다고 하는 편이 낫다
    (`judge.usable_context` 가 그 빈 값을 받아 자동 연결을 막는다).
    """
    needle = (surface or "").strip().casefold()
    if not needle:
        return None
    if title and needle in title.casefold():
        return _trim(title)
    for sentence in sentences(body or ""):
        if needle in sentence.casefold():
            return _trim(sentence)
    return None


def _trim(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= MAX_CONTEXT_CHARS:
        return cleaned
    return cleaned[:MAX_CONTEXT_CHARS].rstrip() + "…"


@dataclass(frozen=True, slots=True)
class ContextPlan:
    """이번 회차에 본문을 읽을 표기와, 저장분을 그대로 쓸 표기.

    `kept` 는 표기 → 저장해 둔 문장이다. 비우거나 제목으로 되돌리지 않고 그 문장을 얹는다 —
    문맥 없는 표기는 판정이 유보로 떨어뜨린다 (`judge.usable_context`).
    """

    wanted: frozenset[tuple[str, str]]
    kept: Mapping[tuple[str, str], str]


def plan(
    counts: Mapping[tuple[str, str], int],
    *,
    min_articles: int,
    context_samples: int,
    stored: Mapping[tuple[str, str], tuple[int, str]],
) -> ContextPlan:
    """표기별 기사 수와 이미 쌓인 표본을 보고 무엇을 읽을지 고른다.

    거르는 것이 둘이다.

    **기사 수 문턱을 못 넘은 표기.** 판정에 오르지 않으니 물어볼 일이 없고, 물어보지 않으면
    문맥도 필요 없다.

    **표본이 이미 찬 표기.** 저장은 표현당 상한이 있어 찬 뒤에는 새 문장이 들어가지 못한다
    (`io/concepts.UNMAPPED_MERGE_SQL`). 그 기사를 또 읽으면 뽑은 문장이 그대로 버려진다.
    본문이 발행일 폴더째로 스캔되는 탓에, 30일에 흩어진 목록 하나가 30일치를 다 읽게 만든다.
    빼고 나면 남는 것이 새로 올라온 표기뿐이라 범위가 최근 며칠로 좁아진다.
    """
    kept = {}
    judged = set()
    for key, articles in counts.items():
        if articles < min_articles:
            continue
        judged.add(key)
        samples, sentence = stored.get(key, (0, ""))
        # **상한이 아니라 뽑을 수 있는 수와 견준다.** 기사 5건짜리 표기는 표본이 다섯을 넘지
        # 못하므로 상한(20)과 견주면 영영 "덜 찼다" 가 되어 매 회차 다시 읽힌다. 미등록
        # 표기의 다수가 그 구간이라 그렇게 두면 이 갈래가 거의 아무것도 못 줄인다.
        if sentence and samples >= min(context_samples, articles):
            kept[key] = sentence
    return ContextPlan(frozenset(judged - set(kept)), kept)
