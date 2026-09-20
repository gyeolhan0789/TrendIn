"""소리키 — 음차 표기와 원어 표기가 같은 키로 모이나.

여기 쌍들은 실 DB 미등록 더미에서 골라온 것이거나 그와 같은 꼴이다. 규칙을 손볼 때 이 표가
깨지면 후보 생성이 조용히 나빠진 것이다.
"""

from __future__ import annotations

import pytest

from trendin.spark.concept.phonetic import MIN_SOUND_KEY, romanize, sound_key

# 소리키가 **똑같이** 나와야 하는 쌍. 후보 생성의 2등급(SOUND)이 여기서 나온다.
SAME = [
    ("샤넬", "Chanel"),
    ("디올", "Dior"),
    ("폴로", "Polo"),
    ("프라다", "Prada"),
    ("에르메스", "Hermes"),
    ("발렌시아가", "Balenciaga"),
    ("보테가베네타", "Bottega Veneta"),
    ("아크네", "Acne"),
    ("데님", "denim"),
    ("シャネル", "Chanel"),
]

# 소리키가 달라야 하는 쌍. 뜻이 다른데 키가 같아지면 후보 목록이 잡음으로 찬다.
DIFFERENT = [
    ("까르띠에", "gold"),
    ("제니", "orange"),
    ("인스타그램", "Tan France"),
    ("스트라이프", "Francis Tien"),
]


@pytest.mark.parametrize(("korean", "latin"), SAME)
def test_음차와_원어가_같은_소리키가_된다(korean: str, latin: str) -> None:
    assert sound_key(korean) == sound_key(latin) != ""


@pytest.mark.parametrize(("left", "right"), DIFFERENT)
def test_다른_말은_다른_소리키다(left: str, right: str) -> None:
    assert sound_key(left) != sound_key(right)


def test_끼워_넣은_모음을_뺀다() -> None:
    # 한국어는 자음만 있는 자리에 `으` 를 넣는다. 그걸 빼야 `stripe` 와 만난다.
    assert sound_key("스트라이프") == "straip"
    # 낱말 첫머리의 `eu` 는 빼지 않는다 — 원어의 모음일 수 있다.
    assert sound_key("Europe").startswith("i")


def test_짧은_키는_주지_않는다() -> None:
    # 두 소리짜리 키는 사전에서 수백 개와 부딪힌다. 빈 문자열은 "쓰지 말라" 는 뜻이다.
    assert sound_key("어그") == ""
    assert len(sound_key("트렌치코트")) >= MIN_SOUND_KEY


def test_이어진_같은_소리는_한_번으로_준다() -> None:
    assert sound_key("폴로") == sound_key("Pollo") == sound_key("Polo")


def test_로마자는_그대로_둔다() -> None:
    assert romanize("Gucci") == "gucci"
    assert romanize("구찌") == "gujji"
    assert romanize("グッチ") == "gucchi"


def test_가나의_요음과_촉음() -> None:
    assert romanize("シャネル") == "shaneru"
    assert romanize("バレエコア") == "bareekoa"
    assert romanize("ボッテガ") == "bottega"
