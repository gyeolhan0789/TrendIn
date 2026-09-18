"""[05] 통합·승격의 **계약** — 구현이 바뀌어도 지켜야 하는 것.

`test_registry_batch.py` 와 나뉘는 기준은 이렇다. 저쪽은 v1 배선이 규칙들을 **어떤 순서로
어떻게 부르는지**를 지키고, 이쪽은 **누가 구현하든 밖에서 같아야 하는 것**만 지킨다. 그래서
이 파일의 시험은 내부 호출을 들여다보지 않는다 — 딱 하나, 병합이 승격보다 먼저라는 것만
호출 순서로 본다. 그것이 [05 §1] 의 불변식이라 밖에서 관측할 방법이 그것뿐이다.

**새 구현은 `IMPLEMENTATIONS` 에 한 줄 더하면 이 파일 전체를 함께 받는다.** 나란히 두고
갈아 끼우는 동안 둘이 같은 계약을 지키는지가 여기서 갈린다.

계약은 넷이다.

| | |
| --- | --- |
| 모양 | 키워드 인자 여섯 개 → `RegistryResult` (`registry/batch.registry_batch` 의 시그니처) |
| 불변식 | 승격은 되돌릴 수 없다 · 병합은 승격 전에만 · 소스 ≥ 2 는 설정으로 못 낮춘다 |
| 승격 생략 | `keywords` 가 `None` 이면 심사는 돌고 적재만 건너뛴다 |
| 관측 | 보류 사유를 `held` 와 `held_by_condition` 두 가지로 남긴다 |
"""

from __future__ import annotations

import pytest
from registry_support import (
    DOMAIN,
    DOMAIN_ENUM,
    RUN_ID,
    FakeKeywords,
    FakeRegistry,
    group,
    observation,
    value_of,
)
from registry_support import make_registry_thresholds as registry_thresholds

from trendin.spark.registry import batch as v1
from trendin.spark.registry import promote
from trendin.spark.registry.merge import signal_of

# 구현 목록. **새것을 여기 더하면 아래 시험 전부가 그것에도 돈다.**
IMPLEMENTATIONS = {"v1": v1.registry_batch}


@pytest.fixture(params=sorted(IMPLEMENTATIONS))
def consolidate(request):
    return IMPLEMENTATIONS[request.param]


def run(consolidate, registry, keywords=None, thresholds=None):
    return consolidate(
        domain=DOMAIN,
        domain_enum=DOMAIN_ENUM,
        thresholds=thresholds or registry_thresholds(),
        registry=registry,
        keywords=keywords,
        extract_run_id=RUN_ID,
    )


# --- 모양 -----------------------------------------------------------------


def test_통과한_후보를_돌려주고_적재한다(consolidate):
    registry = FakeRegistry(observations=[observation("와이드 데님")])
    keywords = FakeKeywords()

    result = run(consolidate, registry, keywords)

    assert result.promoted == ("와이드 데님",)
    assert keywords.promoted == [(DOMAIN, DOMAIN_ENUM, "와이드 데님", "와이드 데님")]


def test_문턱에_못_미치면_적재하지_않는다(consolidate):
    registry = FakeRegistry(
        observations=[observation("와이드 데님", doc_count=1)],
        groups=[group("와이드 데님", doc_count=1)],
    )
    keywords = FakeKeywords()

    result = run(consolidate, registry, keywords)

    assert result.promoted == ()
    assert keywords.promoted == []


# --- 불변식 ---------------------------------------------------------------


def test_이미_승격된_키워드는_심사에서_떨어져도_남는다(consolidate):
    """[05 §1]. 되돌릴 수 없다는 것은 **떨어뜨릴 수도 없다**는 뜻이다 — 문턱을 올리면
    새로 올라오는 것만 줄고, 이미 있는 행은 그대로다."""
    registry = FakeRegistry(
        observations=[observation("와이드 데님", keyword_id=7, doc_count=1, author_count=1)],
        groups=[group("와이드 데님", doc_count=1, author_count=1)],
    )

    result = run(consolidate, registry, FakeKeywords())

    assert result.promoted == ("와이드 데님",)


def test_병합을_반영한_뒤에_심사한다(consolidate):
    """[05 §1] — 병합은 승격 **전**에만 한다. 대표별 관측을 별칭 적재보다 먼저 읽으면
    병합 전 값으로 심사하게 된다."""
    registry = FakeRegistry(
        observations=[observation("와이드 데님"), observation("와이드데님")],
        aliases=[("와이드데님", "와이드 데님", 1, "plural", 1.0, signal_of(plural=True))],
    )

    run(consolidate, registry, FakeKeywords())

    assert registry.calls.index("apply_aliases") < registry.calls.index("group_observations")


def test_별칭으로_흡수된_키는_승격되지_않는다(consolidate):
    """그 관측은 대표에 합산돼 있다. 따로 올리면 같은 것이 두 행이 된다."""
    registry = FakeRegistry(
        observations=[observation("와이드 데님"), observation("와이드데님")],
        aliases=[("와이드데님", "와이드 데님", 1, "plural", 1.0, signal_of(plural=True))],
    )

    result = run(consolidate, registry, FakeKeywords())

    assert "와이드데님" not in result.promoted


def test_소스_하한은_설정으로_낮출_수_없다(consolidate):
    """[05 §3]·[05 §5] 가 못 박은 값이라 `conf` 에 자리가 없다. 나머지를 전부 1 로 풀어도
    소스 하나짜리는 통과하지 못한다."""
    lenient = registry_thresholds(
        promote_min_documents=1,
        promote_min_observed_days=1,
        promote_min_authors=1,
        promote_min_representative_ratio=0.0,
    )
    registry = FakeRegistry(
        observations=[observation("와이드 데님", source_count=1)],
        groups=[group("와이드 데님", source_count=1)],
    )

    result = run(consolidate, registry, FakeKeywords(), thresholds=lenient)

    assert result.promoted == ()


# --- 승격 생략 -------------------------------------------------------------


def test_keywords_가_없으면_심사는_돌고_적재만_건너뛴다(consolidate):
    """분포를 뜨는 실행이 이 갈래다 (`--skip-promotion`). 심사가 함께 멈추면 뜰 자료가
    없어진다."""
    registry = FakeRegistry(observations=[observation("와이드 데님")])

    result = run(consolidate, registry, None)

    assert result.promotion_skipped
    assert result.promoted == ("와이드 데님",)
    assert result.linked_contents == 0


# --- 관측 -----------------------------------------------------------------


def test_보류_사유를_두_가지로_남긴다(consolidate):
    """`held` 는 후보당 하나라 앞선 조건이 뒤를 가리고, `held_by_condition` 은 조건마다
    단독으로 센다. **문턱을 정할 때 보는 것은 뒤쪽이다** ([10 §4] S6).

    지표 이름과 차원 형식은 `pl_batch_stat` 의 집계 키라 구현이 바꿀 수 없다.
    """
    registry = FakeRegistry(
        observations=[observation("와이드 데님", doc_count=1, author_count=1)],
        groups=[group("와이드 데님", doc_count=1, author_count=1)],
    )

    result = run(consolidate, registry, FakeKeywords())

    assert value_of(result, v1.HELD, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1
    assert value_of(result, v1.HELD, f"{DOMAIN}/{promote.HELD_AUTHORS}") == 0
    assert value_of(result, v1.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1
    assert value_of(result, v1.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_AUTHORS}") == 1


def test_사유마다_행을_남긴다(consolidate):
    """0 인 조건도 남긴다 — 좁은 표에서 행이 없는 것은 "안 셌음" 이다 (`io/stats.py`)."""
    registry = FakeRegistry(observations=[observation("와이드 데님")])

    result = run(consolidate, registry, FakeKeywords())

    for reason in promote.HELD_REASONS:
        assert value_of(result, v1.HELD, f"{DOMAIN}/{reason}") is not None
        assert value_of(result, v1.HELD_BY_CONDITION, f"{DOMAIN}/{reason}") is not None
