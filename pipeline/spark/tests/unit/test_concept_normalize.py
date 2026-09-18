"""개념 비교키와 문자 체계 — 라틴·한글 밖의 접기가 여기 걸린다."""

from __future__ import annotations

import pytest

from trendin.spark.concept.normalize import (
    ARABIC,
    HANGUL,
    KANA,
    LATIN,
    LATIN_ANY,
    MIXED,
    OTHER,
    concept_key,
    lang_of_surface,
    latin_fold,
    script_of,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("발레코어", HANGUL),
        ("バレエコア", KANA),
        ("ボッテガ・ヴェネタ", KANA),
        ("بوتيغا فينيتا", ARABIC),
        ("Bottega Veneta", LATIN),
        ("Hermès", LATIN),
        ("MCP는", MIXED),
        ("2026", OTHER),
        ("", OTHER),
    ],
)
def test_문자_체계를_가른다(text, expected):
    assert script_of(text) == expected


def test_한글_가나_아랍은_문자가_언어를_정한다():
    assert lang_of_surface("발레코어", "ja") == "ko"
    assert lang_of_surface("バレエコア", "ko") == "ja"
    assert lang_of_surface("عباءة", "en") == "ar"


def test_라틴은_기사_언어가_라틴_언어일_때만_그_언어다():
    assert lang_of_surface("Bottega Veneta", "fr") == "fr"
    assert lang_of_surface("Bottega Veneta", "it") == "it"
    # 한국·일본 기사 안의 라틴 표기는 언어 무관이다.
    assert lang_of_surface("Bottega Veneta", "ko") == LATIN_ANY
    assert lang_of_surface("Bottega Veneta", None) == LATIN_ANY


def test_일본어_가운뎃점은_키에서_사라진다():
    assert concept_key("ボッテガ・ヴェネタ") == concept_key("ボッテガヴェネタ")
    assert concept_key("ボッテガ･ヴェネタ") == concept_key("ボッテガヴェネタ")  # 반각 가운뎃점


def test_아랍어_타_마르부타와_알리프_변형을_접는다():
    assert concept_key("الموضة") == concept_key("الموضه")
    assert concept_key("أحذية") == concept_key("احذية")


def test_아랍어_발음_부호는_있어도_없어도_같다():
    assert concept_key("مُوضَة") == concept_key("موضه")


def test_아랍어_정관사는_떼지_않는다():
    # `ال` 을 떼면 `Alaïa` 의 아랍어 표기까지 잘린다. 두 표기는 사전에 둘 다 넣는다.
    assert concept_key("الموضة") != concept_key("موضة")


def test_라틴_비교키는_악센트를_그대로_둔다():
    # 키에서 접으면 프랑스어 단어끼리 충돌한다. 2차 키(latin_fold)가 따로 본다.
    assert concept_key("Hermès") == "hermès"
    assert concept_key("déstructuré") != concept_key("destructure")


@pytest.mark.parametrize(
    "key, folded",
    [
        ("hermès", "hermes"),
        ("déstructuré", "destructure"),
        ("œuvre", "oeuvre"),
        ("straße", "strasse"),
        ("gucci", "gucci"),
    ],
)
def test_라틴_2차_키는_악센트와_합자를_접는다(key, folded):
    assert latin_fold(key) == folded


def test_기존_비교키_규칙은_그대로다():
    # extract/keys.normalized_key 가 하던 일 — 소문자 · 하이픈 접기 · 앞뒤 구두점.
    assert concept_key("Ballet-Core") == "ballet core"
    assert concept_key("  BOTTEGA  VENETA, ") == "bottega veneta"
    assert concept_key("") == ""
    assert concept_key(None) == ""
