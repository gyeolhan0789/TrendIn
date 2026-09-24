"""연도·시즌만 다른 표기 — `Vogue World 2026` 은 `Vogue World` 의 한 회차다 (S15P21A102-385).

**2026-09-24 24H 인기 순위 1~4위가 한 행사였다** — `Vogue World` · `Vogue World 2026` ·
`Vogue World Milano 2026` · `Vogue World: Milano`. 층 1·2 는 단수·복수 · 약어 · 오타만 접고,
개념 층의 후보 검색은 사전에 **이미 있는** 개념만 찾는다. 사전에 없던 새 이름이 여러 변형으로
한꺼번에 들어오면 서로 모르는 채로 각자 자리를 차지한다 (NIL clustering 이 없는 자리).

이 모듈은 그중 **글자만 보고 확실히 말할 수 있는 것**만 맡는다 — 끝에 붙은 연도와 컬렉션
시즌 코드다. 문장부호(`Vogue World: Milano`)는 이미 비교키가 접는다 (`extract/keys.py`).

| 표기 | 기준형 | |
| --- | --- | --- |
| `vogue world 2026` | `vogue world` | 연도 |
| `paris fashion week ss27` | `paris fashion week` | 시즌 코드 |
| `prada womenswear ss 2027` | `prada womenswear` | 시즌 표시 + 연도 |
| `2026 멧 갈라` · `멧 갈라 2026년` | `멧 갈라` | 앞의 연도 · `년`/`年` |
| `milano 2026` · `gucci ss27` · `paris ss27` | — | **떼고 한 낱말이 남으면 접지 않는다** |
| `air max 90` · `louis vuitton 1854` | — | 연도 범위(2000~2039) 밖 |
| `vogue world milano` → `vogue world` | — | **낱말은 떼지 않는다** — 의미 판단이 필요하다 |

**떼고 한 낱말이 남는 것은 왜 막나.** 그 한 낱말은 대개 도시·브랜드·일반어다 —
`Milano 2026` 은 동계 올림픽이고 `milano` 는 도시다. 시즌 코드도 마찬가지다 — `Paris SS27` 은
패션위크이고 `paris` 는 도시, `Gucci SS27` 은 컬렉션이고 `gucci` 는 브랜드다. `LFW SS27` 처럼
맞는 경우도 놓치지만 틀린 합산이 더 나쁘다.

⚠️ **두 낱말 장소는 못 막는다.** `Los Angeles 2028`(올림픽) 은 `los angeles` 에 합산된다. 사전
분류에 장소가 없어 가를 근거가 없다 — 장소 판별은 후속(S15P21A102-386)이다. 대신 보이는 이름은
바꾸지 않는다 (`metrics/concepts.py` — 최신 회차 표시는 행사 개념에만).

**앞부분이 같다고 접지 않는다.** `Vogue World` 는 `Vogue` 로 시작하지만 잡지가 아니라
행사다. 떼는 것은 연도·시즌 토큰뿐이고, 남은 기준형이 **글자 그대로 같을 때만** 한 덩이다.

**같은 것이 아니라 같은 집계 단위다.** `Vogue World 2026` 은 시리즈 `Vogue World` 의 한 회차라
영구 별칭(`pl_alias`)으로 붙이지 않고 순위에서만 합친다 (`metrics/concepts.py`). 순위에 보일
이름은 회차가 있으면 가장 최근 회차다 — `edition_order` 가 이름에서 연도·시즌을 읽어 정하므로
언급량이 오르내려도 흔들리지 않는다.

**연도 범위를 좁게 둔 이유** — 모델명·창립 연도가 연도 꼴이다. `Louis Vuitton 1854` ·
`Stone Island 1982` 는 창립 연도를 딴 라인이라 접으면 안 된다. 트렌드 기사가 말하는 회차는
최근 연도라 2000~2039 로 충분하다. `Air Max 2090` 같은 미래 모델명은 범위 밖이다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

import re

# 회차 연도. 앞뒤에 붙는 `년`·`年` 까지 한 토큰으로 본다 (`2026년 멧 갈라`).
_YEAR = re.compile(r"^20[0-3]\d(?:년|年)?$")
# 시즌 코드. 컬렉션 표기에만 쓰는 약어에 두 자리·네 자리 연도가 바로 붙은 꼴이다.
# `ss` spring/summer · `fw`·`aw` fall·autumn/winter · `pf` pre-fall · `rs` resort.
_SEASON_CODE = re.compile(r"^(?:ss|fw|aw|pf|rs)(?:\d{2}|20[0-3]\d)$")
# 연도와 띄어 쓴 시즌 표시 (`ss 2027`, `s/s 2027`). 혼자서는 떼지 않는다 — 연도가 뒤에
# 붙어 있을 때만 시즌 표시다.
_SEASON_MARK = frozenset({"ss", "fw", "aw", "pf", "rs", "s/s", "f/w", "a/w"})


def edition_base(key: str) -> str | None:
    """비교키 → 연도·시즌을 뗀 기준형. 뗄 것이 없거나 떼면 위험하면 `None`.

    `key` 는 `extract/keys.normalized_key` 를 거친 값이다 — 소문자이고 토큰 사이가 공백 하나다.
    """
    tokens = key.split()
    stripped = False
    # 끝에서 뗀다. `ss 2027` 처럼 시즌 표시가 연도 앞에 띄어 있으면 연도를 뗀 뒤에 뗀다.
    while tokens:
        last = tokens[-1]
        if _SEASON_CODE.match(last):
            tokens.pop()
        elif _YEAR.match(last):
            tokens.pop()
            if tokens and tokens[-1] in _SEASON_MARK:
                tokens.pop()
        else:
            break
        stripped = True
    # 앞의 연도는 하나만 뗀다 (`2026 met gala`).
    if tokens and _YEAR.match(tokens[0]):
        tokens.pop(0)
        stripped = True
    if not stripped or not tokens:
        return None
    # 시즌 표시만 남으면 기준형이 아니다 (`2026 s/s`).
    if all(token in _SEASON_MARK for token in tokens):
        return None
    # 문자가 하나도 없으면 이름이 아니다 (`2026 27`).
    if not any(char.isalpha() for token in tokens for char in token):
        return None
    if len(tokens) < 2:
        return None
    return " ".join(tokens)


# 한 해 안의 시즌 순서. 컬렉션이 **보여지는** 순서다 — 리조트(크루즈)가 그해 봄여름보다 먼저 나온다.
_SEASON_RANK = {"rs": 0, "ss": 1, "s/s": 1, "pf": 2, "fw": 3, "aw": 3, "f/w": 3, "a/w": 3}
_CODE = re.compile(r"^(ss|fw|aw|pf|rs)(\d{2}|20[0-3]\d)$")


def edition_order(key: str) -> tuple[int, int] | None:
    """회차의 순서 — `(연도, 시즌 순위)`. 떼어 낼 회차가 없으면 `None`.

    `fw26` < `ss27` 처럼 연도가 먼저고 시즌이 다음이다. 시즌이 없는 연도(`vogue world 2026`)는
    그해 시즌 **앞**으로 둔다 — 순위 `-1`. 여러 개가 붙으면 가장 늦은 것을 쓴다.
    """
    if edition_base(key) is None:
        return None
    tokens = key.split()
    orders: list[tuple[int, int]] = []
    for position, token in enumerate(tokens):
        code = _CODE.match(token)
        if code:
            season, digits = code.groups()
            year = int(digits) if len(digits) == 4 else 2000 + int(digits)
            orders.append((year, _SEASON_RANK[season]))
            continue
        if _YEAR.match(token):
            year = int(token[:4])
            before = tokens[position - 1] if position else ""
            orders.append((year, _SEASON_RANK.get(before, -1)))
    return max(orders) if orders else None


def edition_key(key: str) -> str:
    """같은 덩이를 가르는 열쇠 — 기준형이 있으면 그것, 없으면 자기 자신.

    기준형 자신(`vogue world`)과 그 회차들(`vogue world 2026`)이 같은 열쇠를 갖는다.
    """
    return edition_base(key) or key
