"""언어 판별 ([03 §5]). 층 1 ([09 §4])."""

from __future__ import annotations

import pytest

from trendin.spark.normalize.lang import EN, KO, MIXED, UNKNOWN, LangThresholds, detect_lang


def test_한국어_기사():
    assert detect_lang("이번 시즌 런웨이가 다시 꺼낸 실루엣은 무엇인가") == KO


def test_영어_기사():
    assert detect_lang("The runway silhouette that returned this season") == EN


def test_한글_영문이_섞이면_mixed():
    """**우세 판정보다 먼저 본다.** 한국 패션 매체 기사는 한글 본문에 브랜드명·컬렉션명이
    영문으로 잔뜩 섞이는데, 우세를 먼저 보면 그 기사가 전부 `ko` 가 된다.

    그러면 [04 §2] 가 영문 브랜드명을 한국어 토크나이저로 끊는다 — 이 소스 셋에서 가장
    값진 키워드를.
    """
    assert detect_lang("이번 시즌 Bottega Veneta 의 Intrecciato 백이 돌아왔다") == MIXED


@pytest.mark.parametrize("text", [None, "", "짧다", "2026 F/W", "1234 5678 !!!"])
def test_근거가_없으면_unknown(text):
    """글자 수 하한 미만이다. 없는 근거로 토크나이저를 고르면 후보가 전부 잡음이 된다."""
    assert detect_lang(text) == UNKNOWN


def test_숫자와_기호는_분모에_넣지_않는다():
    """넣으면 표·수치가 많은 기사가 문자 비율이 낮아져 `unknown` 으로 떨어진다.

    실제로는 한국어 기사인데.
    """
    assert detect_lang("2026 F/W 시즌 매출 12,345,678 원 증가 기록 달성") == KO


def test_문턱은_설정에서_온다():
    """[S6] 이 실데이터 분포를 재고 다시 정한다 ([09 §7] 항목 5)."""
    text = "이번 시즌 Bottega 백"

    loose = detect_lang(text, LangThresholds(min_letters=1, secondary=0.2))
    strict = detect_lang(text, LangThresholds(min_letters=1000))

    assert loose == MIXED
    assert strict == UNKNOWN


def test_설정_구역에서_읽는다():
    thresholds = LangThresholds.from_section({"dominant": 0.9, "min_letters": 3})

    assert thresholds.dominant == 0.9
    assert thresholds.min_letters == 3
    # 안 적은 값은 기본값 그대로다.
    assert thresholds.secondary == LangThresholds().secondary


def test_빈_구역이면_기본값이다():
    assert LangThresholds.from_section({}) == LangThresholds()
