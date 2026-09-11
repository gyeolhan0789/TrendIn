"""층 2 — 통계 증거로 병합 ([05 §3]).

| 증거 | 얼마나 강한가 | 이 모듈 |
| --- | --- | --- |
| 약어 ↔ 전개형 | **가장 강하다.** 글쓴이가 "이 둘은 같다" 고 선언한 것 | `abbreviation_pairs` |
| 표기 변형(오타) | 편집 거리 1~2 이고 한쪽 DF 가 압도 | `variant_pairs` |
| 대체 가능성 (NPMI · 문맥) | **증거가 아니라 상관이다.** 검수 큐로 | `registry/review.py` |

**임베딩은 여기 없다** ([05 §4]). "관련 있음" 과 "같음" 을 구분하지 못해 `React`/`Vue` 를
합쳐 버리고, [05 §1] 때문에 그건 되돌릴 수 없다. 층 3 은 후보만 만든다.

**대표는 빈도가 높은 쪽이다.** 약어 쌍에서 대개 약어가 이긴다 ([05 §3]).

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).

## 표기 변형 탐색의 비용

편집 거리는 쌍 단위라 후보 수의 제곱이다. 실측 규모(선별 3,520행 · 비교키 수천~수만)에서
그대로 돌리면 몇 분을 태운다. 그래서 **DF 압도 조건에서 색인 쪽을 유도해 좁힌다** — 흡수되는
쪽의 DF 는 최소 1 이므로, 대표가 되려면 DF 가 `df_dominance` 이상이어야 한다. 그 조건을
만족하는 비교키는 전체의 일부다 (실측에서 DF 상한이 111 이고 대부분의 후보는 2~5).

그래도 색인이 커지면 **건너뛰고 크게 남긴다** (`variant_max_index_size`). 조용히 몇 분을
태우는 것이 가장 나쁘다 — 그때는 배치가 죽은 것도 아니라 아무도 모른다. 그래서
`variant_pairs` 는 쌍만이 아니라 **탐색이 돌았는지**(`VariantScan.skipped`)를 함께 준다 —
쌍이 없는 것과 보지 않은 것이 같은 값이면 그 지표는 "아무도 모른다" 를 막지 못한다.
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from trendin.spark.registry import romanize
from trendin.spark.registry.thresholds import RegistryThresholds

# 근거 층. `pl_merge_log.layer` 에 그대로 들어간다 — **값이 곧 집계 키다.**
LAYER_DETERMINISTIC = 1
LAYER_EVIDENCE = 2

# 규칙 이름. 같은 층 안에서 무엇이 병합을 만들었는지 가른다.
RULE_PLURAL = "plural"
RULE_ABBREVIATION = "abbreviation"
RULE_VARIANT = "variant"


@dataclass(frozen=True, slots=True)
class MergePair:
    """병합 하나. **방향이 있다** — `absorbed` 가 `representative` 로 들어간다.

    `signal` 은 정렬된 JSON 문자열이다. 사전이 아닌 이유는 이 클래스가 frozen·hashable
    이어야 하기 때문이고(집합 연산을 한다), 정렬하는 이유는 같은 근거가 실행마다 같은
    문자열이 되어 `pl_merge_log` 의 diff 가 읽히게 하려는 것이다.
    """

    domain: str
    representative: str
    absorbed: str
    layer: int
    rule: str
    confidence: float
    signal: str

    def reversed(self) -> "MergePair":
        return MergePair(
            domain=self.domain,
            representative=self.absorbed,
            absorbed=self.representative,
            layer=self.layer,
            rule=self.rule,
            confidence=self.confidence,
            signal=self.signal,
        )


@dataclass(frozen=True, slots=True)
class AbbreviationEvidence:
    """`pl_abbreviation_observation` 을 쌍 단위로 접은 것.

    `initials_match` 는 약어의 각 글자가 전개형 단어들의 첫 글자와 대응하는지다 ([05 §3]).
    한국어 전개형은 `false` 이고, 그 쌍은 이 층에서 자동 병합되지 않는다 — 초성 대응이
    없으면 "글쓴이가 같다고 선언했다" 는 증거가 약해진다.
    """

    abbreviation_key: str
    expansion_key: str
    initials_match: bool
    document_count: int
    source_count: int


def observed(df: Mapping[str, int]) -> dict[str, int]:
    """관측이 있는 후보만. **DF 0 은 병합 판정에 참여하지 않는다.**

    `pl_candidate` 는 지우지 않으므로([08 §3]) 관측이 사라진 마스터 행이 남는다. 재추출에서
    DF 문턱에 걸린 후보, 그리고 **토큰화 규칙이 바뀌어 아예 생성되지 않게 된 후보**가 그렇다 —
    2026-09-09 실측에서 fashion 후보 14,444개 중 8,583개가 여기 해당했고, 표본이
    `가고` · `가기` · `가까` 처럼 형태소 분석기로 갈아타기 전 규칙 기반 토큰화가 남긴 어미
    잡음이었다 ([04 §2]).

    그런 후보는 **증거가 없다.** 대표도 흡수 대상도 될 수 없다 — "한쪽 DF 가 압도" 라는 조건
    자체가 성립하지 않고, 0 을 그대로 두면 압도 비율이 0 으로 나눠진다. 그것이 이 함수가
    있는 실질적인 이유이고, 실데이터 리허설에서 드러났다 (손으로 만든 사전에는 없던 경우다).
    """
    return {key: count for key, count in df.items() if count > 0}


def signal_of(**values: object) -> str:
    """근거를 결정적인 JSON 문자열로. `pl_merge_log`·`pl_alias` 가 같은 형식을 쓴다."""
    return json.dumps(values, sort_keys=True, ensure_ascii=False)


def abbreviation_pairs(
    evidence: Iterable[AbbreviationEvidence],
    *,
    domain: str,
    df: Mapping[str, int],
    thresholds: RegistryThresholds,
) -> tuple[MergePair, ...]:
    """약어 ↔ 전개형 자동 병합 ([05 §3]).

    조건은 **소스 2곳 이상**에 더해, 아래 둘 중 **하나**다.

    | 근거 | 무엇 | 언제 |
    | --- | --- | --- |
    | 초성 대응 + 문서 N건 | `Model Context Protocol (MCP)` | 영문 전개형. [05 §3] 의 원래 규약 |
    | **음차 유사도** | `메시카(Messika)` | 한국어 전개형. 초성 대응이 성립하지 않는 자리 |

    **둘째 줄이 2026-09-10 에 늘었다.** 문서 N건 문턱은 "한 사람의 오기가 아님" 을 보려는
    것인데, 브랜드 병기는 괄호에 한두 번 나오고 말아 실측에서 아무것도 통과하지 못했다
    (고유 쌍 275개 중 2회 이상 관측이 8개). 로마자로 편 문자열이 거의 같다는 것은 반복 관측과
    **다른 종류의** 증거이고, 오기로 그런 일치가 나오지 않는다 (`registry/romanize.py`).

    번역(`일상의 사물들(Banal Objects)`)은 유사도에서 떨어진다 — 의도한 동작이다. 음차는 같은
    낱말의 다른 표기라 합치고, 번역은 다른 낱말이라 합치지 않는다.

    **둘 다 후보로 살아남아 있어야 한다.** 한쪽이 [04 §5] 의 필터나 DF 문턱에 걸려 `df` 에
    없거나 관측이 0 이면(`observed`) 합칠 대상이 없다 — 관측은 남아 있으니 다음 배치에서
    다시 본다.

    """
    counts = observed(df)
    pairs: list[MergePair] = []
    for item in sorted(evidence, key=lambda e: (e.abbreviation_key, e.expansion_key)):
        by_initials = (
            item.initials_match
            and item.document_count >= thresholds.abbreviation_min_documents
        )
        # 비교키로 잰다. 대소문자·공백이 접힌 값이라([05 §2]) 표기보다 오히려 안정적이다.
        by_sound = romanize.is_transliteration(
            item.expansion_key, item.abbreviation_key, floor=thresholds.transliteration_floor
        )
        if not (by_initials or by_sound):
            continue
        if item.source_count < thresholds.min_sources:
            continue
        left, right = item.abbreviation_key, item.expansion_key
        if left == right or left not in counts or right not in counts:
            continue
        # 대표는 빈도가 높은 쪽. 동률이면 사전순으로 결정적이게 — 실행마다 대표가 바뀌면
        # `keywords.name` 이 흔들린다.
        representative, absorbed = (
            (left, right) if (counts[left], right) >= (counts[right], left) else (right, left)
        )
        pairs.append(
            MergePair(
                domain=domain,
                representative=representative,
                absorbed=absorbed,
                layer=LAYER_EVIDENCE,
                rule=RULE_ABBREVIATION,
                # 글쓴이의 선언이라 이 층에서 가장 높다.
                confidence=1.0,
                # 어느 근거로 붙었는지 남긴다 — 임계를 바꿨을 때 무엇이 달라졌는지
                # `pl_merge_log` 만 보고 답할 수 있어야 한다.
                signal=signal_of(
                    documents=item.document_count,
                    sources=item.source_count,
                    initials_match=item.initials_match,
                    basis="initials" if by_initials else "transliteration",
                    similarity=round(
                        romanize.similarity(item.expansion_key, item.abbreviation_key), 3
                    ),
                    df_representative=counts[representative],
                    df_absorbed=counts[absorbed],
                ),
            )
        )
    return tuple(pairs)


@dataclass(frozen=True, slots=True)
class VariantScan:
    """변형 탐색 한 번의 결과와 **그것이 실제로 돌았는지** (위 비용 절).

    쌍만 돌려주면 "찾을 것이 없었다" 와 "찾아보지 않았다" 가 같은 값(`()`)이 된다. 상한을
    둔 이유가 후자를 크게 남기려는 것이었으므로 그 둘은 호출자가 갈라야 한다.
    """

    pairs: tuple[MergePair, ...]
    # 색인 쪽(대표가 될 수 있는 후보) 크기. 상한과 견주는 값이라 함께 남긴다.
    index_size: int
    # **상한을 넘겨 탐색을 통째로 건너뛴 경우에만** 참이다. 색인이 비어 쌍이 없는 것은
    # 건너뛴 것이 아니다 — 볼 것이 없었을 뿐이라 경보가 아니다.
    skipped: bool


def variant_pairs(
    df: Mapping[str, int], *, domain: str, thresholds: RegistryThresholds
) -> VariantScan:
    """표기 변형(오타) 흡수 ([05 §3]).

    편집 거리 1~2 이고 한쪽 DF 가 다른 쪽을 `df_dominance` 배 이상 압도하면, 적은 쪽을
    오타로 보고 흡수한다. **짧은 문자열에는 적용하지 않는다** — 4자 이하에서 거리 1은
    딴 낱말인 경우가 흔하다 (`Vue` ↔ `Sue`). **관측이 없는 후보(DF 0)도 보지 않는다**
    (`observed`) — 실측에서 그런 마스터 행이 후보의 60%였다.

    색인이 상한을 넘으면 탐색하지 않고 `skipped` 로 알린다. **색인이 비어 쌍이 없는 것과는
    다른 값이다** — 부른 쪽은 전자만 지표로 남긴다 (`registry/batch.VARIANT_SCAN_SKIPPED`).
    """
    min_length = thresholds.variant_min_length
    max_distance = thresholds.variant_max_edit_distance
    dominance = thresholds.variant_df_dominance

    long_enough = {key: n for key, n in observed(df).items() if len(key) >= min_length}
    # 흡수되는 쪽의 DF 가 최소 1 이므로 대표는 `dominance` 이상이어야 한다. 이 유도가
    # 색인 쪽을 좁힌다 — 위 docstring 의 비용 논의.
    index = sorted(key for key, n in long_enough.items() if n >= dominance)
    if len(index) > thresholds.variant_max_index_size:
        return VariantScan(pairs=(), index_size=len(index), skipped=True)
    if not index:
        return VariantScan(pairs=(), index_size=0, skipped=False)

    pairs: list[MergePair] = []
    for absorbed in sorted(long_enough):
        absorbed_df = long_enough[absorbed]
        for representative in index:
            if representative == absorbed:
                continue
            representative_df = long_enough[representative]
            if representative_df < dominance * absorbed_df:
                continue
            distance = bounded_distance(absorbed, representative, max_distance)
            if distance is None:
                continue
            pairs.append(
                MergePair(
                    domain=domain,
                    representative=representative,
                    absorbed=absorbed,
                    layer=LAYER_EVIDENCE,
                    rule=RULE_VARIANT,
                    # 거리가 멀수록·압도가 약할수록 낮다. 순서를 주는 값이고 확률이 아니다.
                    confidence=round(1.0 / (1 + distance), 4),
                    signal=signal_of(
                        edit_distance=distance,
                        df_representative=representative_df,
                        df_absorbed=absorbed_df,
                        dominance=round(representative_df / absorbed_df, 3),
                    ),
                )
            )
    return VariantScan(pairs=tuple(pairs), index_size=len(index), skipped=False)


def bounded_distance(left: str, right: str, max_distance: int) -> int | None:
    """레벤슈타인 거리. `max_distance` 를 넘으면 `None` — 얼마나 먼지는 안 센다.

    **한글은 자모로 분해해 센다** (NFD). [05 §3] 의 오타 규칙은 라틴 문자 가정인데, 한글은
    한 음절이 음소 두세 개를 담아 **완전히 다른 낱말이 거리 1 로 보인다.**

    | 쌍 | 음절 거리 | 자모 거리 |
    | --- | --- | --- |
    | `데님 셔츠` ↔ `데님 팬츠` (딴 것) | 1 | 3 |
    | `가을 슈즈` ↔ `플랫 슈즈` (딴 것) | 2 | 7 |
    | `플렛 슈즈` ↔ `플랫 슈즈` (오타) | 1 | 1 |

    **2026-09-09 실데이터 리허설에서 잡혔다.** 음절로 세면 위 두 줄이 자동 병합되어
    `데님 셔츠` 가 `데님 팬츠` 로 사라졌다. `variant_min_length` 를 올려도 막지 못한다 —
    이미 5자를 넘는다. 사전으로 개별 패치하지 않고 거리의 정의를 고친 것이고, 라틴 문자는
    NFD 가 건드리지 않으므로 그쪽 동작은 그대로다.

    길이 차가 이미 상한을 넘으면 계산하지 않는다. 이 조기 종료가 위 이중 루프를 감당
    가능하게 만드는 부분이다 — 대부분의 쌍이 첫 줄에서 걸러진다.
    """
    if left == right:
        return 0
    left, right = _phonemes(left), _phonemes(right)
    if abs(len(left) - len(right)) > max_distance:
        return None
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        # 이 행의 최솟값이 상한을 넘었으면 남은 행도 넘는다 (거리는 행마다 줄지 않는다).
        if min(current) > max_distance:
            return None
        previous = current
    distance = previous[-1]
    return distance if distance <= max_distance else None


def _phonemes(text: str) -> str:
    """한글 음절 → 자모. 다른 문자는 그대로다 ([05 §3], 위 표)."""
    return unicodedata.normalize("NFD", text)
