"""비교키 ([04 §4]). 층 1 ([09 §4])."""

from __future__ import annotations

import pytest

from trendin.spark.extract.keys import normalized_key


@pytest.mark.parametrize(
    ("surface", "expected"),
    [
        ("MCP", "mcp"),
        ("Multi-Agent", "multi agent"),
        ("multi_agent", "multi agent"),
        ("multi   agent", "multi agent"),
        ("React.", "react"),
        ("React's", "react"),
        ("React’s hooks", "react hooks"),
        ("ＡＩ Agent", "ai agent"),  # NFKC — 전각 → 반각
        ("#VibeCoding", "vibecoding"),
        ("(Ballet) Sneakers", "ballet sneakers"),
    ],
)
def test_같은_것은_같은_키(surface, expected):
    assert normalized_key(surface) == expected


@pytest.mark.parametrize("surface", ["C++", "C#"])
def test_이름의_일부인_기호는_뒤에서_떼지_않는다(surface):
    """`C++` 와 `C` 는 다른 것이다."""
    assert normalized_key(surface) == surface.lower()


@pytest.mark.parametrize("surface", [None, "", "   ", "---", "..."])
def test_비교키가_비면_후보가_아니다(surface):
    assert normalized_key(surface) == ""


def test_복수형은_접지_않는다():
    """`glasses`→`glasse`, `CSS`→`CS` 같은 과교정. [05 §2] 가 빈도 근거로만 처리한다."""
    assert normalized_key("glasses") == "glasses"
    assert normalized_key("CSS") == "css"
