"""미등록 표기의 문맥은 그 낱말이 실제로 나온 문장이어야 한다."""

from __future__ import annotations

from trendin.spark.concept.context import MAX_CONTEXT_CHARS, find_sentence, sentences

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
