"""[05] 의 단계 배선 (`registry/batch.py`). 층 1.

**이 모듈은 스스로 Spark 를 쓰지 않는다** (`batch.py` 의 docstring) — 입력이 이미 접힌
내부 테이블이라 판정이 순수 파이썬이다. 그래서 가짜 sink 둘이면 층 1 에서 전부 돈다.

여기서 지키는 것은 판정 규칙이 아니라 **배선**이다. 규칙은 `test_registry_{merge,alias,
promote,review,embedding}.py` 가 이미 덮었고, 그 규칙들을 어떤 순서로 · 어떤 대상에 ·
무엇을 세면서 부르는지가 이 파일의 몫이다. 순서가 정확성 조건인 자리가 둘이라
(`batch.py` 의 표) 그 둘이 특히 중요하다.
"""

from __future__ import annotations

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

from trendin.spark.registry import batch, promote
from trendin.spark.registry.merge import signal_of


def run(registry, keywords=None, thresholds=None):
    return batch.registry_batch(
        domain=DOMAIN,
        domain_enum=DOMAIN_ENUM,
        thresholds=thresholds or registry_thresholds(),
        registry=registry,
        keywords=keywords,
        extract_run_id=RUN_ID,
    )


# --- 분모 0 ([09 §4] 이 못 박은 필수 경계) ---------------------------------


def test_그룹_문서_수가_0_이어도_죽지_않는다():
    """`representative_ratio` 의 분모다.

    **방어적인 갈래다** — 오늘의 `GROUP_OBSERVATION_SQL` 은 `count(DISTINCT url_hash)` 라
    행이 있으면 1 이상이고, 그래서 0 은 질의로 나오지 않는다. 그럼에도 덮는 이유는 [09 §4]
    가 "분모 0" 을 필수 경계로 못 박았기 때문이고, 이 값이 배치를 `ZeroDivisionError` 로
    죽이는 자리이기 때문이다 — 도메인 하나가 아니라 실행이 죽는다.
    """
    registry = FakeRegistry(
        observations=[observation("와이드 데님")],
        groups=[group("와이드 데님", doc_count=0)],
    )

    result = run(registry, FakeKeywords())

    assert result.promoted == ()
    assert value_of(result, batch.HELD, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1


# --- 승격 관문 밖의 통계 ---------------------------------------------------


def test_승격이_막히면_1_을_남기고_연결도_하지_않는다():
    """`keywords` 가 `None` 인 회차. 심사는 그대로 돌고 승격만 건너뛴다."""
    registry = FakeRegistry(observations=[observation("와이드 데님")])

    result = run(registry, None)

    assert result.promotion_skipped
    assert result.promoted == ("와이드 데님",), "심사는 돌아야 한다 — 막힌 것은 승격뿐이다"
    assert value_of(result, batch.PROMOTION_SKIPPED) == 1
    assert value_of(result, batch.PROMOTED) == 0
    assert result.linked_contents == 0


def test_승격이_돌면_0_을_남긴다():
    registry = FakeRegistry(observations=[observation("와이드 데님")])
    keywords = FakeKeywords()

    result = run(registry, keywords)

    assert value_of(result, batch.PROMOTION_SKIPPED) == 0
    assert keywords.promoted == [(DOMAIN, DOMAIN_ENUM, "와이드 데님", "와이드 데님")]
    assert result.linked_contents == 2


def test_후보가_없는_도메인도_통계를_남긴다():
    """빈손으로 돌아가면 그 도메인만 `promotion_skipped` 가 0 도 1 도 아니게 된다.

    좁은 표에서는 **행이 없는 것이 곧 "안 셌음"** 이라(`io/stats.py`), 빠진 값과 0 을
    나중에 구분할 수 없다 — 상수 주석이 약속한 0/1 이 깨지는 자리다.
    """
    result = run(FakeRegistry(observations=[]), None)

    assert value_of(result, batch.CANDIDATES) == 0
    assert value_of(result, batch.PROMOTION_SKIPPED) == 1
    assert result.promoted == ()


# --- 변형 탐색을 건너뛴 것 -------------------------------------------------


def test_색인_상한을_넘긴_회차에만_1_이다():
    """상한을 둔 이유가 "조용히 건너뛴 것을 크게 남긴다" 였다 (`merge.py` 의 비용 절)."""
    keys = [f"키워드{index:04d}" for index in range(5)]
    registry = FakeRegistry(observations=[observation(key, doc_count=100) for key in keys])

    over = run(registry, None, registry_thresholds(variant_max_index_size=2))

    assert value_of(over, batch.VARIANT_SCAN_SKIPPED) == 1


def test_쌍이_안_나온_정상_회차는_0_이다():
    """여기가 1 이면 지표가 정상 상태와 같은 값을 내고, 그때부터 경보가 아니다."""
    keys = [f"키워드{index:04d}" for index in range(5)]
    registry = FakeRegistry(observations=[observation(key, doc_count=100) for key in keys])

    normal = run(registry, None)

    assert value_of(normal, batch.VARIANT_SCAN_SKIPPED) == 0


# --- 순서가 정확성 조건인 자리 (`batch.py` 의 표) --------------------------


def test_별칭을_반영한_뒤에_대표별_관측을_읽는다():
    """4 → 5. 먼저 읽으면 병합 전 값으로 심사한다."""
    registry = FakeRegistry(
        observations=[
            observation("에이전트", doc_count=30),
            observation("에이전트들", doc_count=3),
        ],
        groups=[group("에이전트", doc_count=33)],
        aliases=[("에이전트들", "에이전트", 1, "plural", 1.0, signal_of(plural=True))],
    )

    run(registry, FakeKeywords())

    assert registry.calls.index("apply_aliases") < registry.calls.index("group_observations")
    assert registry.calls.index("observations") < registry.calls.index("apply_aliases")


def test_별칭은_심사하지_않는다():
    """그 관측은 대표에 합산돼 있다 — 따로 심사하면 같은 문서를 두 번 센다."""
    registry = FakeRegistry(
        observations=[
            observation("에이전트", doc_count=30),
            observation("에이전트들", doc_count=3),
        ],
        groups=[group("에이전트", doc_count=33)],
        aliases=[("에이전트들", "에이전트", 1, "plural", 1.0, signal_of(plural=True))],
    )
    keywords = FakeKeywords()

    result = run(registry, keywords)

    assert result.promoted == ("에이전트",)
    assert [row[2] for row in keywords.promoted] == ["에이전트"]


# --- 층 3 ------------------------------------------------------------------


def test_모델이_없으면_임베딩을_아예_만지지_않는다():
    """`conf` 기본이 `model: null` 이다 — 그 상태에서 캐시를 읽으면 빈 모델 이름이 샌다."""
    registry = FakeRegistry(
        observations=[observation("와이드 데님"), observation("와이드 팬츠")]
    )

    result = run(registry, FakeKeywords())

    assert registry.encoded_models == []
    assert value_of(result, batch.EMBEDDING_ENCODED) == 0


# --- 조건별 분포 ([10 §4] S6 가 요구하는 자료) -----------------------------


def test_조건마다_단독으로_막은_수를_따로_센다():
    """`HELD` 는 후보당 사유 하나라 앞선 조건이 뒤를 가린다 (`registry/promote.Verdict`).

    승격 문턱은 가려진 쪽을 봐야 정할 수 있어서 `HELD_BY_CONDITION` 이 따로 있다. 이
    시험이 지키는 것은 **두 표가 같은 심사에서 나오되 다르게 세어진다**는 것이다.
    """
    registry = FakeRegistry(
        observations=[observation("와이드 데님", doc_count=1, author_count=1)],
        groups=[group("와이드 데님", doc_count=1, author_count=1)],
    )

    result = run(registry, FakeKeywords())

    assert result.promoted == ()
    # 사유는 `HELD_REASONS` 순서의 첫 번째 하나만 — 저자 수도 걸렸지만 0 이다.
    assert value_of(result, batch.HELD, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1
    assert value_of(result, batch.HELD, f"{DOMAIN}/{promote.HELD_AUTHORS}") == 0
    # 조건별로는 둘 다 센다. **합이 보류 수를 넘는다** — 그것이 이 지표의 성질이다.
    assert value_of(result, batch.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1
    assert value_of(result, batch.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_AUTHORS}") == 1


def test_막지_않은_조건도_0_으로_행을_남긴다():
    """좁은 표에서는 행이 없는 것이 곧 "안 셌음" 이다 (`io/stats.py`). 0 과 부재가 같아
    보이면 "이 조건은 아무것도 막지 않는다" 를 읽어낼 수 없다."""
    registry = FakeRegistry(observations=[observation("와이드 데님")])

    result = run(registry, FakeKeywords())

    assert result.promoted == ("와이드 데님",)
    for reason in promote.HELD_REASONS:
        assert value_of(result, batch.HELD_BY_CONDITION, f"{DOMAIN}/{reason}") == 0


def test_이미_승격된_후보는_조건별_분포에서_뺀다():
    """떨어져도 되돌리지 않으므로([05 §1]) 섞으면 "지금 무엇이 막고 있나" 가 흐려진다 —
    알고 싶은 것은 아직 올라오지 못한 쪽이다."""
    registry = FakeRegistry(
        observations=[
            observation("와이드 데님", keyword_id=7, doc_count=1, author_count=1),
            observation("카고 팬츠", doc_count=1, author_count=1),
        ],
        groups=[
            group("와이드 데님", doc_count=1, author_count=1),
            group("카고 팬츠", doc_count=1, author_count=1),
        ],
    )

    result = run(registry, FakeKeywords())

    assert result.promoted == ("와이드 데님",), "이미 승격된 것은 떨어져도 통과로 남는다"
    assert value_of(result, batch.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_DOCUMENTS}") == 1
    assert value_of(result, batch.HELD_BY_CONDITION, f"{DOMAIN}/{promote.HELD_AUTHORS}") == 1
