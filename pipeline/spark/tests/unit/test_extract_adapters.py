"""언어별 후처리 (`extract/adapters.py`). 층 1 ([09 §4]).

**형태소 분석기를 실제로 부른다.** kiwipiepy 는 C++ 확장이라 JVM·torch 없이 호스트에서
돌고, 조사 판정이야말로 이 파일이 지키려는 것이라 가짜 분석기로는 아무것도 증명되지 않는다.
"""

from __future__ import annotations

from trendin.spark.extract.adapters import AdapterSpec, refine
from trendin.spark.extract.entities import Span
from trendin.spark.normalize.lang import EN, JA, KO, MIXED

SPEC = AdapterSpec()


def span(surface: str, label: str = "브랜드", score: float = 0.9, start: int = 0) -> Span:
    return Span(surface=surface, label=label, score=score, start=start, end=start + len(surface))


def surfaces(spans, lang, *, spec: AdapterSpec = SPEC) -> list[str]:
    return [item.surface for item in refine(spans, lang, spec=spec)]


# --- 한국어 — 조사 제거가 성능의 절반이다 -------------------------------------------


def test_조사를_뗀다():
    got = surfaces([span("제니가"), span("데님 팬츠가"), span("컬렉션의")], KO)
    assert got == ["제니", "데님 팬츠", "컬렉션"]


def test_부호도_꼬리로_본다():
    assert surfaces([span("샤넬,"), span("(프라다)")], KO) == ["샤넬", "(프라다"]


def test_명사가_없으면_버린다():
    """꼬리 제거만으로는 안 걸리는 둘 — 접속부사와 용언 활용형."""
    assert surfaces([span("그리고"), span("부드러운"), span("샤넬")], KO) == ["샤넬"]


def test_조사가_없으면_그대로다():
    assert surfaces([span("오버사이즈 재킷")], KO) == ["오버사이즈 재킷"]


def test_라틴_표기는_분석기에_넘기지_않는다():
    """`Brooks Brothers` 가 `BrooksBrothers` 로 붙는 것을 막는다 (`MULTILINGUAL.md` §3)."""
    assert surfaces([span("Brooks Brothers"), span("Miu Miu")], KO) == [
        "Brooks Brothers",
        "Miu Miu",
    ]


def test_혼합_문서도_한국어_경로다():
    assert surfaces([span("샤넬의"), span("Chanel")], MIXED) == ["샤넬", "Chanel"]


# --- 영어 — 공백만 접는다 -----------------------------------------------------------


def test_줄바꿈을_접는다():
    """GLiNER 가 문단을 넘어 잡으면 표기에 줄바꿈이 남는다."""
    assert surfaces([span("bias-cut slip\ndress")], EN) == ["bias-cut slip dress"]


def test_영어는_형태소를_거치지_않는다():
    assert surfaces([span("The Row"), span("wide-leg trousers")], EN) == [
        "The Row",
        "wide-leg trousers",
    ]


# --- 일본어 — 반만 켠다 -------------------------------------------------------------


def test_브랜드와_인물만_통과시킨다():
    got = surfaces(
        [span("ケンゾー", "브랜드"), span("尾花大輔", "인물"), span("スウェット", "의류 품목")],
        JA,
    )
    assert got == ["ケンゾー", "尾花大輔"]


def test_길이_상한이_절을_막는다():
    """원본 구간의 32~60% 가 절이었다 (`MULTILINGUAL.md` §2.3)."""
    clause = "ケンゾーのヘリテージとモダンな感性を重ね合わせたタイガーグラフィックのシリーズ"
    assert surfaces([span(clause, "브랜드"), span("ケンゾー", "브랜드")], JA) == ["ケンゾー"]


def test_라벨_제한이_없는_언어는_전부_통과한다():
    got = surfaces([span("Chanel", "브랜드"), span("silk scarves", "의류 품목")], EN)
    assert len(got) == 2


def test_라벨_제한을_설정으로_늘릴_수_있다():
    spec = AdapterSpec(label_gates=((JA, ("브랜드", "인물", "의류 품목")),))
    got = surfaces([span("スウェット", "의류 품목")], JA, spec=spec)
    assert got == ["スウェット"]


# --- 공통 -------------------------------------------------------------------------


def test_시작_위치를_유지하고_끝만_줄인다():
    """`document.py` 가 `start` 로 제목 출현을 가른다 — 꼬리를 떼도 앞은 그대로여야 한다."""
    (refined,) = refine([span("제니가", start=17)], KO, spec=SPEC)
    assert refined.start == 17 and refined.end == 17 + len("제니")


def test_점수와_라벨은_그대로_간다():
    (refined,) = refine([span("샤넬의", "브랜드", 0.93)], KO, spec=SPEC)
    assert (refined.label, refined.score) == ("브랜드", 0.93)


def test_빈_목록():
    assert refine([], KO, spec=SPEC) == []
