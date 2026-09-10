"""검수 큐 ([05 §7]). 층 1.

**`REJECTED` 를 다시 올리지 않는 것**이 이 파일의 핵심이다. 기록하지 않으면 같은 쌍이 매
배치마다 다시 큐에 올라와 검수자를 지치게 한다 — 그러면 아무도 큐를 안 보고, 그때부터
층 3 은 있으나 없으나가 된다.
"""

from __future__ import annotations

from trendin.spark.registry import review
from trendin.spark.registry.merge import (
    LAYER_EVIDENCE,
    RULE_ABBREVIATION,
    MergePair,
    signal_of,
)
from trendin.spark.registry.review import LAYER_EMBEDDING

DOMAIN = "fashion"
DF = {"agent": 30, "에이전트": 12, "mcp": 40, "model context protocol": 9}


def parked_pair() -> MergePair:
    return MergePair(
        domain=DOMAIN,
        representative="mcp",
        absorbed="model context protocol",
        layer=LAYER_EVIDENCE,
        rule=RULE_ABBREVIATION,
        confidence=1.0,
        signal=signal_of(documents=5),
    )


def embedding_pair(similarity: float = 0.88) -> MergePair:
    return MergePair(
        domain=DOMAIN,
        representative="agent",
        absorbed="에이전트",
        layer=LAYER_EMBEDDING,
        rule="embedding",
        confidence=similarity,
        signal=signal_of(similarity=similarity, npmi=None),
    )


def test_우선순위는_두_후보의_문서_수_합이고_큰_것이_먼저다():
    """**영향이 큰 것부터** ([05 §7])."""
    items = review.review_items(
        parked=[parked_pair()], embedding_pairs=[embedding_pair()], doc_counts=DF
    )

    assert [item.priority for item in items] == [49, 42]
    assert items[0].absorbed_key == "model context protocol"


def test_판단이_끝난_쌍은_다시_올리지_않는다():
    decided = [(DOMAIN, "agent", "에이전트")]

    items = review.review_items(embedding_pairs=[embedding_pair()], doc_counts=DF, decided=decided)

    assert items == ()


def test_보류된_층2_쌍은_층2_신호가_있다고_표시된다():
    """[05 §4] 의 표에서 "유사도 높음 + 층 2 증거 있음" 은 자동 병합이라 큐에 오지 않는다.
    보류된 쌍은 증거가 있는데도 오므로 그 구분이 필요하다."""
    items = review.review_items(parked=[parked_pair()], doc_counts=DF)

    assert items[0].has_layer2_signal
    assert items[0].origin == review.ORIGIN_PARKED


def test_임베딩_후보는_유사도를_들고_오고_NPMI_는_비어_있다():
    """**NPMI 는 [06] 이 계산하고 그건 다음 에픽이다** (`registry/embedding.py`)."""
    items = review.review_items(embedding_pairs=[embedding_pair(0.91)], doc_counts=DF)

    assert items[0].similarity == 0.91
    assert items[0].npmi is None
    assert not items[0].has_layer2_signal


def test_같은_쌍이_두_갈래로_와도_한_행이다():
    items = review.review_items(
        parked=[parked_pair()], embedding_pairs=[parked_pair()], doc_counts=DF
    )

    assert len(items) == 1


def test_승인된_쌍은_병합으로_되읽힌다():
    """**다음 `extract` 실행부터 적용된다** ([05 §7])."""
    pairs = review.approved_pairs([(DOMAIN, "mcp", "model context protocol")])

    assert [(pair.representative, pair.absorbed) for pair in pairs] == [
        ("mcp", "model context protocol")
    ]
    assert pairs[0].rule == review.RULE_REVIEW
    assert pairs[0].confidence == 1.0


def test_자기_자신_쌍은_승인이어도_버린다():
    assert review.approved_pairs([(DOMAIN, "mcp", "mcp")]) == ()
