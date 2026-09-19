"""언어 판별 ([03 §5]). 층 1 ([09 §4])."""

from __future__ import annotations

import pytest

from trendin.spark.normalize.lang import (
    EN,
    FR,
    IT,
    JA,
    KO,
    MIXED,
    UNKNOWN,
    ZH,
    LangThresholds,
    detect_lang,
    unsupported,
)


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


# --- 알아보지만 추출하지 않는 언어 -------------------------------------------


def test_일본어_문단():
    text = (
        "パリで開かれたショーで、デザイナーは新しいコレクションを発表した。"
        "今季は素材の質感を前面に出し、色使いを抑えたという。"
    )
    assert detect_lang(text) == JA


def test_일본어_제목은_짧아도_알아본다():
    """한 글자가 담는 정보가 많다. 한글·라틴 글자 수 하한(10)을 걸면 여기서 `unknown` 이 되고,
    제목만 있는 문서는 필터를 지나 한국어 분석기를 탄다."""
    assert detect_lang("新作バッグが登場") == JA


def test_일본어에_영문_브랜드명이_섞여도_일본어다():
    assert detect_lang("Louis Vuittonの2026年秋冬コレクションが発表された") == JA


def test_중국어_문단():
    text = "这家品牌在上海发布了新的秋冬系列。设计师表示，这一季更注重可持续材料和手工工艺。"
    assert detect_lang(text) == ZH


def test_프랑스어_문단():
    text = (
        "La maison a présenté sa nouvelle collection à Paris. Les créations sont inspirées "
        "par les années soixante et la directrice artistique explique que cette saison est "
        "très importante pour elle."
    )
    assert detect_lang(text) == FR


def test_이탈리아어_문단():
    text = (
        "La maison ha presentato la nuova collezione a Milano. Le creazioni sono ispirate "
        "agli anni sessanta e il direttore creativo spiega che questa stagione è molto "
        "importante per il marchio."
    )
    assert detect_lang(text) == IT


@pytest.mark.parametrize(
    "title",
    [
        "Show HN: A de facto standard for La Liga match stats",
        "Cost per token is falling faster than anyone expected",
        "Le Chat: Mistral launches a new assistant for the web",
        "Pros and cons of running Postgres per tenant",
        "Ask HN: Is anyone using Rust in production at a large company?",
        "The Carbon Footprint of La Sagrada Familia",
        "Non-profit open source maintainers need better funding",
        "De Gaulle's plan for a European nuclear deterrent, revisited",
    ],
)
def test_hn_영어_제목은_뒤집히지_않는다(title):
    """dev 도메인 전량이 `hn` 제목이다. 영어가 아니게 판별되면 필터가 통째로 버린다."""
    assert detect_lang(title) == EN


def test_한자를_병기한_한국어_기사는_한국어로_남는다():
    assert detect_lang("정부는 美 관세 조치에 대응해 中 수출 규제를 검토하고 있다고 밝혔다") == KO


def test_한글과_영문_브랜드명은_이전처럼_mixed():
    assert detect_lang("루이 비통 Louis Vuitton 2026 가을 겨울 컬렉션 공개") == MIXED


@pytest.mark.parametrize("lang", [KO, EN, MIXED, UNKNOWN, JA, ZH, FR, IT])
def test_알아보는_언어는_모두_추출한다(lang):
    """2026-09-19 부터 `LANGUAGES` 의 여섯이 전부 `extractable` 이다. 그전에는
    `ja`·`zh`·`fr`·`it` 가 `True` 였고, 그 표가 일본·이탈리아·프랑스·중국 매체를 통째로
    버리고 있었다.

    `unknown` 이 여기 `False` 인 것은 뜻이 다르다 — 언어가 아니라 근거 부족이라 `LANGUAGES`
    에 들지 않고, 필터가 `UNKNOWN_LANG` 으로 따로 다룬다.
    """
    assert unsupported(lang) is False


def test_설정_구역에서_읽는다():
    thresholds = LangThresholds.from_section(
        {"dominant": 0.9, "min_letters": 3, "latin_min_hits": 7, "kana_share": 0.5}
    )

    assert thresholds.dominant == 0.9
    assert thresholds.min_letters == 3
    assert thresholds.latin_min_hits == 7
    assert thresholds.kana_share == 0.5
    # 안 적은 값은 기본값 그대로다.
    assert thresholds.secondary == LangThresholds().secondary


def test_빈_구역이면_기본값이다():
    assert LangThresholds.from_section({}) == LangThresholds()
