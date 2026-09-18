"""층 5 — 승격 심사 ([05 §5]).

후보가 `keywords` 로 들어가는 관문이고, **이 묶음에서 가장 보수적인 지점이다.** 한 번
들어가면 사실상 되돌릴 수 없다 ([05 §1]) — 행 하나에 사용자의 관심 키워드 · 트렌드 ·
언급량 시계열 · 관련 콘텐츠 · 연관 관계가 딸려 있어 삭제가 어느 정책으로도 나쁘게 끝난다.

| 조건 | 무엇을 막나 |
| --- | --- |
| 누적 문서 수 ≥ 하한 | 일회성 |
| 관측 일수 ≥ 하한 (연속일 필요 없음) | 하루 반짝하는 이벤트 · 스팸 |
| 서로 다른 **소스** ≥ 2 | 한 커뮤니티의 은어 |
| 서로 다른 **저자** ≥ 하한 | **봇 · 자기홍보** |
| `dup_of` 가 있는 문서를 제외한 기준 | 크로스포스트로 부풀린 것 |
| 대표 표기 비율 ≥ 하한 | 표기가 안 잡힌 것 |

**저자 다양성이 가장 중요하다** ([05 §5]). 자동 발견이 실패하는 대표적 형태가 "한 사람이
자기 프로젝트 이름을 30개 글에 뿌린 것" 이 신규 트렌드로 올라오는 것이다 — 문서 수만 보면
통과하지만 저자 수를 보면 1 이다.

**보류는 손실이 아니다.** 보류된 후보는 `pl_candidate` 에 `CANDIDATE` 로 남아 다음 배치에서
다시 심사된다. 하루 늦게 잡히는 것은 문제가 아니지만 잘못 승격된 것은 영구히 남는다.

## `dup_of` 와 대표 표기 비율이 어디서 오나

`doc_count` · `source_count` · `author_count` 는 `pl_document_candidate` 를 직접 센 값이다
(`io/keywords.OBSERVATION_SQL` · `GROUP_OBSERVATION_SQL`). 그 질의가 `is_dup` 문서를 빼므로
여기서 다시 걸러낼 것이 없다 — 다섯째 조건은 조달 쪽에서 이미 충족돼 있다.

**`pl_keyword_daily_stat` 이 아니다.** 일별 원자료에도 같은 이름의 칸이 있지만 그쪽은 날짜와
**국가**로 쪼개져 있어(2026-09-18) 더하면 유일 개수가 아니라 합이 된다. 심사가 그 표를 읽게
되면 날짜와 국가를 먼저 접어야 한다.

**대표 표기 비율은 병합 그룹 기준으로 읽는다.** [05 §5] 의 원문은 표기 분포를 뜻하지만
문서별 원표기가 저장되지 않는다 — [04] 가 코퍼스 대표 표기 하나로 접어 `pl_document_candidate`
에 넣기 때문이다. 그래서 **그룹 전체 문서 수 중 대표 후보의 몫**으로 잰다. 표기가 갈려
별칭이 대표만큼 흔한 그룹의 승격을 미루는 것이고, 원래 조건이 막으려던 "표기가 안 잡힌 것"
과 같은 것을 막는다. 별칭이 없는 후보는 비율이 1.0 이다.

**pyspark 를 import 하지 않는다** ([09 §4] 층 1).
"""

from __future__ import annotations

from dataclasses import dataclass

from trendin.spark.registry.thresholds import RegistryThresholds

# 보류 사유. **값이 곧 집계 키다** — `pl_batch_stat` 의 차원으로 나가므로 바꾸면 옛 실행과
# 이어지지 않는다. 여러 조건에 걸리면 이 목록 순서대로 첫 번째 하나만 남긴다.
HELD_DOCUMENTS = "held/documents"
HELD_OBSERVED_DAYS = "held/observed_days"
HELD_SOURCES = "held/sources"
HELD_AUTHORS = "held/authors"
HELD_REPRESENTATIVE_RATIO = "held/representative_ratio"
PROMOTED = "promoted"

HELD_REASONS = (
    HELD_DOCUMENTS,
    HELD_OBSERVED_DAYS,
    HELD_SOURCES,
    HELD_AUTHORS,
    HELD_REPRESENTATIVE_RATIO,
)


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    """후보 하나의 누적 관측. 병합이 끝난 뒤의 **대표** 기준이다.

    별칭의 관측이 대표에 합산돼 있다 — `registry/batch.py` 가 `pl_alias` 를 거쳐 묶는다.
    `dup_of` 문서는 `pl_keyword_daily_stat` 이 이미 뺐다 ([08 §3]).
    """

    domain: str
    key: str
    surface: str
    doc_count: int
    observed_days: int
    source_count: int
    author_count: int
    representative_ratio: float


@dataclass(frozen=True, slots=True)
class Verdict:
    """심사 결과. 보류도 사유를 남긴다 — 남기지 않으면 "왜 안 올라오지" 에 답할 수 없다."""

    promoted: bool
    reason: str
    # 걸린 조건 **전부**. `reason` 은 이 중 첫 번째다.
    #
    # 둘을 따로 두는 이유는 **세는 목적이 다르기 때문**이다. `reason` 은 `pl_batch_stat` 의
    # 차원이라 후보당 하나여야 하고(아래 `judge` 의 "사유는 하나만"), 그래서 앞선 조건이
    # 뒤를 가린다 — 2026-09-17 실행에서 보류 1,263건 중 1,262건이 `held/documents` 였고
    # 나머지 넷은 전부 0 이었는데, 그 0 은 "막을 것이 없다" 가 아니라 "세지 않았다" 였다.
    # **승격 문턱은 그 표로 정할 수 없다** ([10 §4] S6 가 요구하는 후보 분포가 이 자리다).
    # `failed` 는 조건마다 따로 세라고 있는 것이라 합이 보류 수를 넘는다.
    failed: tuple[str, ...] = ()


def judge(evidence: PromotionEvidence, thresholds: RegistryThresholds) -> Verdict:
    """승격 여부와 사유. **모든 조건을 함께 만족해야 통과한다** ([05 §5]).

    **가중합이 아니라 AND 다.** 조건마다 막으려는 것이 서로 다르고([05 §5] 의 표) 하나가
    다른 하나를 보상할 수 없다 — 문서 30건이 저자 1명을 상쇄하지 못한다. 점수로 합치면
    "문서가 아주 많으면 저자 하나라도 통과" 가 되는데, 그게 바로 자동 발견이 실패하는
    대표적 형태다.

    **경계는 통과 쪽이다.** 규격이 "≥ 하한" 이라고 적었으므로 `<` 로만 막는다.

    **`reason` 은 하나만 남긴다.** `HELD_REASONS` 순서대로 첫 번째다 — 이 값이
    `pl_batch_stat` 의 차원이 되므로([05 §5] 의 분포 모니터링) 여러 개를 남기면 "무엇이 가장
    많이 막는가" 의 합이 후보 수를 넘어 읽을 수 없는 숫자가 된다.

    **걸린 조건 전부는 `Verdict.failed` 에 따로 담는다.** 문턱을 정하려면 조건마다 단독으로
    무엇을 막는지 알아야 하는데 `reason` 하나로는 그것을 셀 수 없다 (`Verdict` 의 주석).
    조건을 **더 보게 된 것이 아니라** — 아래는 예나 지금이나 다섯을 전부 본다 — 본 결과를
    버리지 않게 된 것이다.

    **저자 정보가 없는 소스가 붙으면 여기가 다시 온다.** 지금은 실측 373건 전부에 `author`
    가 있고 고유 저자가 78명이라 AND 로 두어도 막히지 않는다. 그 값이 늘 비는 소스가
    생기면 그 소스의 문서는 이 관문을 영구히 통과하지 못하고, 그때 필요한 것은 문턱을
    낮추는 것이 아니라 **소스별로 저자 조건을 다루는 것**이다 — 낮추면 봇 방어가 통째로
    풀린다. 결론이 나기 전에는 이 상태가 맞다 ([05 §5] "의심스러우면 보류한다").
    """
    failed = _failures(evidence, thresholds)
    if failed:
        return Verdict(promoted=False, reason=failed[0], failed=failed)
    return Verdict(promoted=True, reason=PROMOTED)


def _failures(evidence: PromotionEvidence, thresholds: RegistryThresholds) -> tuple[str, ...]:
    """걸리는 조건을 **전부**. 순서는 `HELD_REASONS` 그대로다.

    **판정이 있는 곳은 여기 하나다.** `judge` 가 조건을 따로 적으면 둘이 갈리고, 갈린 쪽이
    이기는지는 호출 경로에 달린다 — `Verdict.failed` 를 세는 쪽과 `reason` 을 세는 쪽이
    서로 다른 규칙으로 돌면 두 표를 나란히 놓을 수 없다.
    """
    failed: list[str] = []
    if evidence.doc_count < thresholds.promote_min_documents:
        failed.append(HELD_DOCUMENTS)
    if evidence.observed_days < thresholds.promote_min_observed_days:
        failed.append(HELD_OBSERVED_DAYS)
    if evidence.source_count < thresholds.min_sources:
        failed.append(HELD_SOURCES)
    if evidence.author_count < thresholds.promote_min_authors:
        failed.append(HELD_AUTHORS)
    if evidence.representative_ratio < thresholds.promote_min_representative_ratio:
        failed.append(HELD_REPRESENTATIVE_RATIO)
    return tuple(failed)
