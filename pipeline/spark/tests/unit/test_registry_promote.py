"""승격 관문 ([05 §5]). 층 1.

**이 파일이 `registry/promote.judge` 의 실행 가능한 규격이다.** 여섯 조건이 함께 걸리는지,
보류 사유가 하나만 남는지, 경계값이 통과 쪽인지를 지킨다.

승격은 되돌릴 수 없으므로([05 §1]) 여기서 통과시키면 안 되는 것을 통과시키는 것이 이
묶음에서 가장 비싼 실수다. 반대로 보류는 손실이 아니다 — 다음 배치에서 다시 심사된다.
"""

from __future__ import annotations

import pytest
from registry_support import make_registry_thresholds as registry_thresholds

from trendin.spark.registry import promote
from trendin.spark.registry.promote import PromotionEvidence

DOMAIN = "fashion"


def evidence(**overrides) -> PromotionEvidence:
    """문턱을 딱 만족하는 후보. 시험마다 한 칸만 깎아 그 조건이 걸리는지 본다."""
    values = dict(
        domain=DOMAIN,
        key="와이드 데님",
        surface="와이드 데님",
        doc_count=5,
        observed_days=2,
        source_count=2,
        author_count=3,
        representative_ratio=0.6,
    )
    values.update(overrides)
    return PromotionEvidence(**values)


def test_모든_조건을_경계값으로_만족하면_통과한다():
    """경계는 **통과 쪽**이다 — 규격이 "≥ 하한" 이라고 적었다 ([05 §5])."""
    verdict = promote.judge(evidence(), registry_thresholds())

    assert verdict.promoted
    assert verdict.reason == promote.PROMOTED


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"doc_count": 4}, promote.HELD_DOCUMENTS),
        ({"observed_days": 1}, promote.HELD_OBSERVED_DAYS),
        ({"source_count": 1}, promote.HELD_SOURCES),
        ({"author_count": 2}, promote.HELD_AUTHORS),
        ({"representative_ratio": 0.59}, promote.HELD_REPRESENTATIVE_RATIO),
    ],
)
def test_조건_하나만_모자라도_보류하고_사유를_남긴다(override, reason):
    verdict = promote.judge(evidence(**override), registry_thresholds())

    assert not verdict.promoted
    assert verdict.reason == reason


def test_저자가_하나면_문서가_많아도_보류한다():
    """**자동 발견이 실패하는 대표적 형태** ([05 §5]) — 한 사람이 자기 프로젝트 이름을
    30개 글에 뿌린 것. 문서 수만 보면 통과하지만 저자 수를 보면 1이다."""
    verdict = promote.judge(
        evidence(doc_count=30, observed_days=10, source_count=3, author_count=1),
        registry_thresholds(),
    )

    assert not verdict.promoted
    assert verdict.reason == promote.HELD_AUTHORS


def test_여러_조건에_걸리면_사유는_하나만_남는다():
    """통계 차원이 하나여야 "무엇이 가장 많이 막는가" 를 셀 수 있다 (`registry/promote.py`).

    순서는 `HELD_REASONS` 그대로다.
    """
    verdict = promote.judge(
        evidence(doc_count=1, observed_days=1, source_count=1, author_count=1),
        registry_thresholds(),
    )

    assert verdict.reason == promote.HELD_DOCUMENTS
    assert verdict.reason in promote.HELD_REASONS


def test_소스_하한은_규격이_고정한_2_다():
    """설정으로 낮출 값이 아니다 ([05 §3]·[05 §5], `registry/thresholds.MIN_SOURCES`)."""
    lenient = registry_thresholds(promote_min_documents=1, promote_min_observed_days=1)

    assert not promote.judge(evidence(source_count=1), lenient).promoted
    assert promote.judge(evidence(source_count=2), lenient).promoted
