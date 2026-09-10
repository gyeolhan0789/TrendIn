"""층 1 — 결정적 규칙 ([05 §2]).

**대부분은 이미 `extract/keys.py` 에 있다.** NFKC · 대소문자 접기 · 하이픈·언더스코어·연속
공백 → 단일 공백 · 앞뒤 구두점 제거 · 소유격 제거가 비교키 생성에서 적용된다. [05 §2] 의
표는 그 규칙의 **정의 위치**이고 구현 위치는 [04 §4] 다.

**여기 남는 것은 복수형 하나다.** 그것만 코퍼스를 봐야 하기 때문이다 — `-s`/`-es` 제거는
과교정이 잦아서(`CSS`→`CS`, `glasses`→`glasse`) 규칙으로 밀 수 없고, **양쪽 표기가 모두
코퍼스에 존재하고 한쪽 DF 가 다른 쪽을 압도할 때만** 접는다. 증거를 보므로 판정 형태는
층 2 와 같고, 그래서 `MergePair` 를 공유한다. 층 번호만 1 로 남긴다.

**한국어 복수형(`-들`)은 여기 오지 않는다** ([05 §2]). [04 §2] 의 형태소 분석기가
`아이템들` 을 `아이템`(NNG) + `들`(XSN) 로 갈라 표기에서 빼기 때문이다 (표기 정책
`prefixed`). 그 정책을 `word` 로 바꾸면 이 층으로 넘어오는데, 2026-09-09 실측에서
`사람들`(35문서) 대 `사람`(71) 처럼 **양쪽이 다 흔한** 쌍은 아래 압도 조건을 만족하지
못해 접히지 않는다 — 토큰화에서 접는 것이 여기서 접는 것보다 싸다는 판단의 근거다.

**조사가 붙은 표기는 더 이상 오지 않는다** ([05 §2], 2026-09-09). 조사는 후보의 재료가
아니라 경계이므로 비교키에 남지 않는다. 남은 예외는 분석기가 모르는 고유명사가 조사째
한 덩이가 되는 것(`메종마르지엘라의`)이고, 1차 방어는 사용자 사전이며 그것을 빠져나온
것은 위 표기 변형(`registry/merge.variant_pairs`)이 받는다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from collections.abc import Mapping

from trendin.spark.registry.merge import (
    LAYER_DETERMINISTIC,
    RULE_PLURAL,
    MergePair,
    observed,
    signal_of,
)
from trendin.spark.registry.thresholds import RegistryThresholds

# 떼어 볼 접미사. 긴 것부터 본다 — `glasses` 에서 `es` 를 먼저 떼면 `glass` 가 나온다.
_SUFFIXES = ("es", "s")


def plural_pairs(
    df: Mapping[str, int], *, domain: str, thresholds: RegistryThresholds
) -> tuple[MergePair, ...]:
    """조건부 복수형 접기 ([05 §2]).

    **마지막 토큰에서만 뗀다.** 비교키는 여러 낱말일 수 있고(`ai agents`), 복수는 늘
    끝에 붙는다. 앞 토큰까지 건드리면 `agents list` 를 `agent list` 로 바꾸는 일이
    생기는데 그건 다른 낱말이다.

    **양쪽이 다 흔하면 접지 않는다.** 압도 조건이 그것을 막는다 — 근거 없이 규칙으로
    밀지 않는 것이 이 절의 취지다.
    """
    dominance = thresholds.plural_df_dominance
    # 관측이 없는 후보(DF 0)는 양쪽 다 제외한다 — 증거가 없고, 압도 비율이 0 으로 나눠진다
    # (`merge.observed`. 2026-09-09 실데이터 리허설에서 드러났다).
    counts = observed(df)
    pairs: list[MergePair] = []
    for plural in sorted(counts):
        for singular in _singular_forms(plural):
            if singular not in counts:
                continue
            plural_df, singular_df = counts[plural], counts[singular]
            # 대표는 압도한 쪽이다. 복수형이 더 흔한 낱말도 있다 (`glasses`).
            if singular_df >= dominance * plural_df:
                representative, absorbed = singular, plural
            elif plural_df >= dominance * singular_df:
                representative, absorbed = plural, singular
            else:
                continue
            pairs.append(
                MergePair(
                    domain=domain,
                    representative=representative,
                    absorbed=absorbed,
                    layer=LAYER_DETERMINISTIC,
                    rule=RULE_PLURAL,
                    confidence=1.0,
                    signal=signal_of(
                        singular=singular,
                        plural=plural,
                        df_representative=counts[representative],
                        df_absorbed=counts[absorbed],
                        dominance=round(counts[representative] / counts[absorbed], 3),
                    ),
                )
            )
            # 한 복수형에 단수 후보가 둘 다 존재하는 경우(`es` · `s`)에는 긴 접미사 쪽만
            # 쓴다. 둘을 다 내면 같은 표기가 두 대표를 갖는다.
            break
    return tuple(pairs)


def _singular_forms(plural: str) -> tuple[str, ...]:
    """`-es` → `-s` 순서로 후보를 낸다. 마지막 토큰만 바꾼다."""
    head, _, last = plural.rpartition(" ")
    prefix = f"{head} " if head else ""
    forms: list[str] = []
    for suffix in _SUFFIXES:
        if len(last) > len(suffix) and last.endswith(suffix):
            forms.append(f"{prefix}{last[: -len(suffix)]}")
    return tuple(forms)
