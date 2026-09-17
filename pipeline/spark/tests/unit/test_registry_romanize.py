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


# --- 받침 표가 어긋나면 잡는다 (2026-09-16) -------------------------------------
#
# `_FINAL` 에 원소가 하나 모자라 종성 20(ㅆ) 이후가 한 칸씩 밀려 있었다. ㅇ 받침이 `ng` 가
# 아니라 `j` 로 나왔고, 마지막 ㅎ 받침은 `IndexError` 로 **Job 을 통째로 죽였다**
# (`extract` 2026-09-16). 위 음차/번역 표본이 전부 받침 없는 이름이거나 ㄴ·ㄹ 받침이라
# 유사도 경계만 보는 검사로는 드러나지 않았다 — 그래서 로마자 값을 직접 본다.


def test_모든_한글_음절이_로마자로_펴진다():
    """11,172자 전부. 표 길이가 어긋나면 여기서 `IndexError` 로 걸린다."""
    for code in range(0xAC00, 0xD7A4):
        romanize(chr(code))


@pytest.mark.parametrize(
    "한글, 로마자",
    [
        ("강남", "gangnam"),  # ㅇ 받침 — 가장 흔하고, 밀림이 여기서 먼저 드러난다
        ("명동", "myeongdong"),
        ("쌍문", "ssangmun"),  # ㅆ 초성 + ㅇ 받침
        ("좋은", "joheun"),  # ㅎ 받침 — 표의 마지막 자리
        # ㅆ 받침. 발음은 [t] 지만 이 모듈은 자모를 그대로 펴므로 ㅅ 받침과 같이 `s` 다
        # (모듈 docstring 의 "완전한 로마자 표기법이 아니다").
        ("갔다", "gasda"),
        ("꽃", "kkoc"),  # ㅊ 받침
        ("부엌", "bueok"),  # ㅋ 받침
        ("밭", "bat"),  # ㅌ 받침
        ("앞", "ap"),  # ㅍ 받침
    ],
)
def test_받침이_제자리에_있다(한글, 로마자):
    assert romanize(한글) == 로마자
