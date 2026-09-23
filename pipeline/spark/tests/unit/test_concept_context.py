"""미등록 표기의 문맥은 그 낱말이 실제로 나온 문장이어야 한다."""

from __future__ import annotations

from trendin.spark.concept.context import MAX_CONTEXT_CHARS, find_sentence, plan, sentences

BODY = (
    "가을 신상이 쏟아졌다. 플리츠 스커트가 올해 다시 눈에 띈다. "
    "특히 교복 같은 플리츠는 신발과의 궁합이 중요하다."
)


def test_제목에_있으면_제목을_쓴다() -> None:
    """편집자가 직접 고른 요약이라 본문 아무 문장보다 낫다."""
    title = "플리츠 스커트, 신발이 관건"
    assert find_sentence(BODY, title, "플리츠") == title


def test_제목에_없으면_본문_첫_등장_문장을_쓴다() -> None:
    """뒤로 갈수록 짧아지거나 대명사로 바뀐다 — 첫 언급이 가장 풀어서 쓴다."""
    found = find_sentence(BODY, "올가을 이건 꼭 사세요", "플리츠")
    assert found == "플리츠 스커트가 올해 다시 눈에 띈다."


def test_어디에도_없으면_비운다() -> None:
    """엉뚱한 제목을 문맥이라고 넘기느니 없다고 하는 편이 낫다 — 운영 제목의 91%가 그랬다."""
    assert find_sentence(BODY, "Famous Guys Are Going Blonde", "ken") is None
    assert find_sentence(None, None, "플리츠") is None
    assert find_sentence(BODY, None, "  ") is None


def test_대소문자를_가리지_않는다() -> None:
    body = "Coach, the Tapestry-owned label, posted a 21% gain."
    assert find_sentence(body, "Tapestry earnings", "coach") == body


def test_긴_문장은_잘라_넘긴다() -> None:
    """프롬프트에 그대로 실리는 값이라 상한이 있어야 한다."""
    body = "플리츠 " + "아주 긴 설명 " * 200
    found = find_sentence(body, None, "플리츠")
    assert found is not None
    assert len(found) <= MAX_CONTEXT_CHARS + 1
    assert found.endswith("…")


def test_문장_경계는_동아시아_부호도_본다() -> None:
    assert sentences("첫 문장이다。두 번째다！셋째？") == ["첫 문장이다。두 번째다！셋째？"]
    assert sentences("First. Second! Third?") == ["First.", "Second!", "Third?"]
    assert sentences("줄바꿈도\n경계다") == ["줄바꿈도", "경계다"]


# --- 무엇을 읽을지 고르는 자리 ---------------------------------------------
#
# 본문은 발행일 폴더째로 스캔된다. 읽을 목록에서 빼는 것이 곧 스캔 범위를 줄이는 것이라
# 여기가 이 Job 시간의 거의 전부다.

THRESHOLDS = {"min_articles": 2, "context_samples": 3}
COAT = ("ko", "코트")
BALACLAVA = ("ko", "바라클라바")
SENTENCE = "겨울 코트가 다시 팔린다."


def test_표본이_찬_표기는_읽지_않고_저장분을_쓴다() -> None:
    """읽어 봐야 상한에 걸려 버려진다. 대신 저장해 둔 문장을 얹는다."""
    chosen = plan(
        {COAT: 5, BALACLAVA: 4}, **THRESHOLDS, stored={COAT: (3, SENTENCE)}
    )
    assert chosen.wanted == frozenset({BALACLAVA})
    assert chosen.kept == {COAT: SENTENCE}


def test_표본이_모자라면_다시_읽는다() -> None:
    """상한에 아직 여유가 있으면 이번에 뽑은 문장이 실제로 저장된다."""
    chosen = plan({COAT: 5}, **THRESHOLDS, stored={COAT: (2, SENTENCE)})
    assert chosen.wanted == frozenset({COAT})
    assert chosen.kept == {}


def test_기사보다_많은_표본은_있을_수_없다() -> None:
    """기사 2건짜리 표기는 표본이 둘을 넘지 못한다.

    상한(3)과 견주면 영영 "덜 찼다" 가 되어 매 회차 다시 읽힌다. 미등록의 다수가 이 구간이라
    그렇게 두면 이 갈래가 거의 아무것도 못 줄인다.
    """
    chosen = plan({COAT: 2}, **THRESHOLDS, stored={COAT: (2, SENTENCE)})
    assert chosen.wanted == frozenset()
    assert chosen.kept == {COAT: SENTENCE}


def test_표본_수만_차고_문장이_비었으면_다시_읽는다() -> None:
    """빈 문장을 얹으면 판정이 문맥 없는 표기가 되어 유보로 떨어진다."""
    chosen = plan({COAT: 5}, **THRESHOLDS, stored={COAT: (9, "")})
    assert chosen.wanted == frozenset({COAT})
    assert chosen.kept == {}


def test_기사_수_문턱을_못_넘으면_아예_빠진다() -> None:
    """판정에 오르지 않는다. 물어보지 않으니 문맥도 필요 없다."""
    chosen = plan({COAT: 1}, **THRESHOLDS, stored={})
    assert chosen.wanted == frozenset()
    assert chosen.kept == {}
