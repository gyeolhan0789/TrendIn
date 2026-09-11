"""증가량·증가율·순위 — [07 §5]."""

from __future__ import annotations

from datetime import date

import pytest

from trendin.spark.metrics.growth import (
    MetricRow,
    assign_ranks,
    build_row,
    growth_amount,
    growth_rate,
)

START = date(2026, 9, 3)
END = date(2026, 9, 10)


def row(keyword_id: int, mentions: int, previous: int, *, domain: str = "fashion") -> MetricRow:
    return build_row(
        keyword_id=keyword_id,
        domain=domain,
        period="7D",
        period_start=START,
        period_end=END,
        mention_count=mentions,
        previous_mention_count=previous,
    )


# --- 증가량 ---------------------------------------------------------------


def test_증가량은_음수가_될_수_있다():
    assert growth_amount(0, 100) == -100


def test_하락한_키워드도_행을_갖는다():
    """100 → 0 은 `growth_amount = −100` 이라는 정보다. 행이 없으면 화면에서 그냥 사라진다."""
    dropped = row(1, 0, 100)
    assert dropped.growth_amount == -100
    assert dropped.growth_rate == -100.0


# --- 증가율 ---------------------------------------------------------------


def test_직전이_0_이면_증가율이_None_이다():
    """무한대나 큰 수로 채우지 않는다. `None` 은 "계산 불가(전에 없었음)" 다."""
    assert growth_rate(5, 0) is None
    assert row(1, 5, 0).growth_rate is None


def test_둘_다_0_이어도_None_이다():
    assert growth_rate(0, 0) is None


def test_소수_첫째_자리로_반올림한다():
    assert growth_rate(1, 3) == -66.7
    assert growth_rate(2, 3) == -33.3
    assert growth_rate(7, 3) == 133.3


def test_증가율만_보면_뒤집히는_쌍():
    """3 → 9 (200%) 가 500 → 700 (40%) 을 앞선다. `RISING` 이 증가량도 함께 보는 이유다."""
    assert row(1, 9, 3).growth_rate > row(2, 700, 500).growth_rate
    assert row(1, 9, 3).growth_amount < row(2, 700, 500).growth_amount


# --- 순위 -----------------------------------------------------------------


def test_언급량_내림차순으로_순위를_매긴다():
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(1, 5, 1), row(2, 9, 1), row(3, 7, 1)]
    )}
    assert ranked == {2: 1, 3: 2, 1: 3}


def test_공동_순위를_두지_않는다():
    """`mention_rank` 가 페이징 기준이라 같은 등수가 여럿이면 총 페이지 수가 틀어진다."""
    ranks = [item.mention_rank for item in assign_ranks([row(1, 5, 1), row(2, 5, 1)])]
    assert sorted(ranks) == [1, 2]


def test_동점이면_증가율이_높은_쪽이_위다():
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(1, 5, 4), row(2, 5, 1)]  # 25% vs 400%
    )}
    assert ranked == {2: 1, 1: 2}


def test_증가율이_None_이면_뒤로_간다():
    """`DESC NULLS LAST` — 전에 없던 키워드가 동점에서 위로 올라오지 않는다."""
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(1, 5, 0), row(2, 5, 4)]
    )}
    assert ranked == {2: 1, 1: 2}


def test_전부_동점이면_keyword_id_순이다():
    """**결정적이어야 한다.** 데이터가 안 변했는데 실행마다 순위가 흔들리면 그게 화면에
    "순위 변동" 으로 나타난다."""
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(9, 5, 5), row(2, 5, 5), row(7, 5, 5)]
    )}
    assert ranked == {2: 1, 7: 2, 9: 3}


def test_같은_입력이면_같은_순서로_돌려준다():
    rows = [row(9, 5, 5), row(2, 7, 1), row(7, 5, 5), row(4, 0, 3)]
    first = [item.keyword_id for item in assign_ranks(rows)]
    second = [item.keyword_id for item in assign_ranks(list(reversed(rows)))]
    assert first == second


def test_언급량_0_인_행은_순위가_None_이다():
    """넣을 값이 없다 — 0 도 아니고 마지막 등수도 아니다(그 등수가 매 실행 달라진다)."""
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(1, 3, 1), row(2, 0, 100)]
    )}
    assert ranked == {1: 1, 2: None}


def test_0_인_행이_순위를_소비하지_않는다():
    ranked = {item.keyword_id: item.mention_rank for item in assign_ranks(
        [row(1, 0, 9), row(2, 3, 1), row(3, 1, 1)]
    )}
    assert ranked == {2: 1, 3: 2, 1: None}


def test_순위_범위가_도메인별로_갈린다():
    """`(domain, period)` 안에서 매긴다 ([07 §5]). 개발의 `모델` 과 패션의 `모델` 은 다르다."""
    ranked = {
        (item.domain, item.keyword_id): item.mention_rank
        for item in assign_ranks(
            [row(1, 5, 1), row(2, 9, 1, domain="dev"), row(3, 3, 1, domain="dev")]
        )
    }
    assert ranked == {("fashion", 1): 1, ("dev", 2): 1, ("dev", 3): 2}


def test_후보가_하나뿐이어도_돈다():
    assert [item.mention_rank for item in assign_ranks([row(1, 1, 0)])] == [1]


def test_빈_목록이면_빈_목록이다():
    assert assign_ranks([]) == []


@pytest.mark.parametrize("mentions, previous", [(0, 1), (1, 0), (0, 0)])
def test_경계값에서_죽지_않는다(mentions, previous):
    built = row(1, mentions, previous)
    assert built.growth_amount == mentions - previous
