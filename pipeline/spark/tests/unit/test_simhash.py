"""SimHash 지문 ([03 §6] 3단계). 층 1 ([09 §4]).

표적은 두산매거진 4곳(`vogue`·`gqkorea`·`wkorea`·`allure`)의 **같은 보도자료 동시 게재**다.
그건 `article_id` 도 URL 도 달라서 지문 말고는 잡히지 않는다.
"""

from __future__ import annotations

import pytest

from trendin.spark.normalize.dedup import DedupThresholds
from trendin.spark.normalize.simhash import (
    BITS,
    hamming,
    shingles,
    simhash,
    to_signed64,
    tokenize,
)

BASE = (
    "보테가 베네타가 2026 가을겨울 컬렉션을 공개했다. "
    "인트레치아토 기법을 재해석한 백과 미니멀한 실루엣의 코트가 중심이다. "
    "브랜드는 이번 시즌 색채를 절제하고 소재의 질감을 앞세웠다고 밝혔다."
)
# 무관한 주제의 글. 지문이 벌려야 하는 쪽이다.
OTHER = (
    "쿠버네티스 1.32 가 릴리스됐다. 사이드카 컨테이너가 정식 기능이 되고 "
    "동적 리소스 할당이 베타로 올라갔다. 업그레이드 전 확인할 항목을 정리한다."
)
# 같은 보도자료를 가볍게 손봐 실은 것. 3단계가 잡아야 하는 표적이다.
REPOSTED = "[보도자료] " + BASE.replace("밝혔다", "전했다")


def test_같은_글은_지문이_같다():
    assert simhash(BASE) == simhash(BASE)



def test_같은_글이_다른_글보다_훨씬_가깝다():
    """**이것이 지문이 지켜야 하는 성질이다.** 절대 거리는 문서 길이와 편집량에 따라
    움직이지만, 이 간격은 움직이지 않는다.

    문턱의 절대값은 [S6] 이 실데이터로 정한다 ([09 §7] 항목 5). 그래서 여기서는 간격만
    고정하고, 문턱이 그 간격 안에 있는지는 아래 테스트가 본다.
    """
    near = hamming(simhash(BASE), simhash(REPOSTED))
    far = hamming(simhash(BASE), simhash(OTHER))

    assert near * 3 < far


def test_동일_본문은_거리가_0_이다():
    """**3단계가 반드시 잡아야 하는 경우다.** 다른 매체가 보도자료를 그대로 실으면 본문이
    같고 `article_id` 와 URL 만 다르다 — 1·2 단계에는 안 걸린다.

    문턱이 무엇이든 0 은 잡힌다. 그래서 이것이 문턱과 무관하게 성립하는 유일한 표적이다.
    """
    assert hamming(simhash(BASE), simhash(BASE)) == 0


def test_기본_문턱이_두_군집_사이에_있다():
    """**2026-09-08 측정을 고정한다** (`dedup.DedupThresholds` 의 표).

    가벼운 편집 쌍이 8~13, 무관한 글이 31~40 이었다. 문턱은 그 사이에 있어야 한다 —
    아래로 내리면 3단계가 놀고, 위로 올리면 서로 다른 기사를 묶어 언급량이 줄고 그게
    잘못된 하락 판별이 된다 ([07 §5]).

    이 테스트가 깨지면 기본값이나 지문 계산이 바뀐 것이고, 둘 다 [03 §6] 3단계가 무엇을
    잡는지를 바꾸므로 근거를 다시 재야 한다.
    """
    limit = DedupThresholds().max_distance

    assert hamming(simhash(BASE), simhash(REPOSTED)) <= limit
    assert hamming(simhash(BASE), simhash(OTHER)) > limit


def test_머리말만_붙은_경우는_더_가깝다():
    """편집이 적을수록 가까워진다 — 지문이 편집량에 반응한다는 뜻이다."""
    prefix_only = hamming(simhash(BASE), simhash("[보도자료] " + BASE))
    edited = hamming(simhash(BASE), simhash(REPOSTED))

    assert prefix_only <= edited


def test_기호만_다른_것은_지문에_들어가지_않는다():
    """토큰이 한글·라틴·숫자의 연속이라 따옴표 종류가 바뀌어도 같은 특징이 나온다."""
    assert tokenize("‘런웨이’ — 실루엣!") == tokenize("\"런웨이\" - 실루엣?")


def test_표기_차이를_무시한다():
    """지문 토큰은 문서가 같은지만 판단하고 후보가 되지 않으므로 소문자로 접어도 된다."""
    assert tokenize("Bottega VENETA") == ["bottega", "veneta"]


@pytest.mark.parametrize("text", [None, "", "   ", "!!!"])
def test_특징이_없으면_None(text):
    assert simhash(text) is None


def test_토큰이_shingle_보다_적으면_전체를_하나로_본다():
    assert shingles(["가", "나"], size=3) == ["가 나"]
    assert shingles([], size=3) == []


def test_지문이_없으면_안_닮은_것으로_본다():
    """**`None` 을 0(완전 동일)으로 접으면** 지문 없는 문서끼리 서로 중복으로 판별된다.

    본문 없는 문서가 dev 도메인 전량이라([03 §2]) 그 실수는 도메인 하나를 통째로 지운다.
    """
    assert hamming(None, simhash(BASE)) == BITS
    assert hamming(simhash(BASE), None) == BITS
    assert hamming(None, None) == BITS


def test_부호_변환이_해밍_거리를_바꾸지_않는다():
    """`LongType` 은 부호 있는 64비트라 지문 절반이 상한을 넘는다. 그대로 넣으면 조용히
    `null` 이 되거나 배치가 죽는다.

    `hamming` 이 XOR 결과를 마스크로 자르므로 변환된 값을 그대로 넣어도 결과가 같다.
    """
    left, right = simhash(BASE), simhash("[보도자료] " + BASE)

    assert hamming(to_signed64(left), to_signed64(right)) == hamming(left, right)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (0, 0),
        (1, 1),
        ((1 << 63) - 1, (1 << 63) - 1),  # 상한 바로 아래는 그대로
        (1 << 63, -(1 << 63)),  # 상한부터 음수로 접힌다
        ((1 << 64) - 1, -1),
    ],
)
def test_부호_변환_경계(value, expected):
    assert to_signed64(value) == expected


def test_변환_결과가_bigint_범위에_든다():
    fingerprint = to_signed64(simhash(BASE))

    assert -(1 << 63) <= fingerprint <= (1 << 63) - 1
