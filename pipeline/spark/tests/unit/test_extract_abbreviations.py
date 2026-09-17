"""`전개형 (약어)` 관측 (`extract/abbreviations.py`). 층 1 ([09 §4]).

후보 생성이 실체 인식으로 옮겨진 뒤에도 이 탐지는 그대로다 — 모델은 "이 둘이 같은 것" 이라고
말해 주지 않는다. 옛 `test_extract_candidates.py` 에서 옮겨 왔다 (2026-09-16).
"""

from __future__ import annotations

import pytest

from trendin.spark.extract import abbreviations as abbr


def test_영문_전개형과_약어의_첫_글자가_맞으면_기록한다():
    (pair,) = abbr.abbreviation_pairs("the Model Context Protocol (MCP) is here")

    assert pair.abbreviation == "MCP"
    assert pair.expansion == "Model Context Protocol"  # 앞의 `the` 는 전개형이 아니다
    assert pair.expansion_key == "model context protocol"
    assert pair.initials_match is True


def test_기능어를_건너뛰어_맞춘다():
    (pair,) = abbr.abbreviation_pairs("Retrieval of Augmented Generation (RAG)")
    assert pair.expansion == "Retrieval of Augmented Generation" and pair.initials_match


def test_첫_글자가_안_맞으면_기록하지_않는다():
    assert abbr.abbreviation_pairs("some random words (XYZ)") == []


def test_한국어_전개형은_대응을_볼_수_없어_표시만_남긴다():
    (pair,) = abbr.abbreviation_pairs("MCP는 모델 컨텍스트 프로토콜(MCP)의 약자다")

    assert pair.expansion == "모델 컨텍스트 프로토콜"  # 앞의 `MCP는` 은 빠진다
    assert pair.initials_match is False


def test_이름꼴_병기도_남긴다():
    """[05 §3] 이 "가장 강한 증거" 로 꼽은 형태다 — 브랜드 음차 병기."""
    (pair,) = abbr.abbreviation_pairs("메시카(Messika)의 하이주얼리 컬렉션")

    assert (pair.expansion, pair.abbreviation) == ("메시카", "Messika")
    # 이름꼴은 초성 대응이 성립하지 않는다. 음차 유사도가 대신 근거가 된다.
    assert pair.initials_match is False


@pytest.mark.parametrize("text", [None, "", "no parens here", "(MCP)"])
def test_쌍이_없으면_빈_목록(text):
    assert abbr.abbreviation_pairs(text) == []
