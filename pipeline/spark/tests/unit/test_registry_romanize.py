"""음차 유사도 — [05 §3] 의 브랜드 병기를 잇는 근거.

**이 파일이 지키는 경계는 하나다** — 음차는 합치고 번역은 합치지 않는다.
"""

from __future__ import annotations

import pytest

from trendin.spark.registry.romanize import (
    DEFAULT_SIMILARITY_FLOOR,
    is_transliteration,
    romanize,
    similarity,
)

# 실제 코퍼스에서 나온 괄호 병기 (2026-09-10, fashion 376문서).
음차 = [
    ("메시카", "Messika"),
    ("아크리스", "Akris"),
    ("캘빈 클라인", "Calvin Klein"),
    ("낸 골딘", "Nan Goldin"),
    ("소우 후지모토", "Sou Fujimoto"),
    ("이노 마사유키", "Ino Masayuki"),
]
# 같은 자리에서 나왔지만 **번역**이다. 합치면 안 된다.
번역 = [
    ("일상의 사물들", "Banal Objects"),
    ("황소 가죽", "Bull Leather"),
    ("순환성", "circularity"),
    ("심장", "coeur"),
]


def test_한글을_로마자로_편다():
    assert romanize("메시카") == "mesika"
    assert romanize("아크리스") == "akeuriseu"


def test_한글이_아닌_글자는_소문자로_남는다():
    assert romanize("MCP") == "mcp"
    assert romanize("발레 슈즈") == "balresyujeu"


def test_빈_문자열은_0_이다():
    assert similarity("", "Messika") == 0.0
    assert similarity("메시카", "") == 0.0


def test_기호만_있으면_0_이다():
    assert similarity("···", "!!!") == 0.0


@pytest.mark.parametrize("korean, latin", 음차)
def test_음차는_통과한다(korean, latin):
    점수 = similarity(korean, latin)
    assert is_transliteration(korean, latin), f"{korean} ↔ {latin} = {점수:.2f}"


@pytest.mark.parametrize("korean, latin", 번역)
def test_번역은_떨어진다(korean, latin):
    """**결함이 아니라 원하는 동작이다.** 번역을 합치면 "어느 표기가 어디서 먼저 떴나" 를
    물을 대상이 사라진다."""
    assert not is_transliteration(korean, latin)


def test_음차와_번역이_겹치지_않는다():
    """두 무리가 임계 하나로 갈리는지 — 겹치면 임계를 고르는 일이 성립하지 않는다."""
    붙는다 = min(similarity(korean, latin) for korean, latin in 음차)
    안붙는다 = max(similarity(korean, latin) for korean, latin in 번역)
    assert 붙는다 > 안붙는다


def test_방향이_바뀌어도_같다():
    """괄호 병기는 보통 `한글(라틴)` 이지만 반대도 온다."""
    assert similarity("메시카", "Messika") == similarity("Messika", "메시카")


def test_무관한_쌍은_낮다():
    assert similarity("샤넬", "Balenciaga") < DEFAULT_SIMILARITY_FLOOR
    assert similarity("발레 슈즈", "ballet flats") < DEFAULT_SIMILARITY_FLOOR


def test_임계를_올리면_더_깐깐하다():
    assert is_transliteration("캘빈 클라인", "Calvin Klein", floor=0.5)
    assert not is_transliteration("캘빈 클라인", "Calvin Klein", floor=0.9)
