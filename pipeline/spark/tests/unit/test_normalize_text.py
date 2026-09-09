"""텍스트 정제 ([03 §4]). 층 1 ([09 §4]).

규격이 순서를 못 박은 일곱 단계라, 여기 테스트는 **순서가 지켜지는지**를 본다. 각 단계가
따로 동작하는지는 순서가 틀렸을 때도 통과하므로 그것만으로는 부족하다.
"""

from __future__ import annotations

import pytest

from trendin.spark.normalize.text import (
    clean_text,
    clean_title,
    collapse_whitespace,
    split_code,
)

# --- 단계 1·2 순서 -------------------------------------------------------


def test_코드_분리가_태그_제거보다_먼저다():
    """태그를 먼저 지우면 `<` 가 든 코드가 태그로 보여 함께 사라진다."""
    body, code = split_code("<p>앞</p><pre>if (a &lt; b) { x(); }</pre>")

    assert code == "if (a < b) { x(); }"
    assert "if" not in clean_text(body)


def test_태그_제거가_엔티티_디코드보다_먼저다():
    """뒤집으면 본문에 적힌 `&lt;script&gt;` 가 진짜 태그가 되어 다음 단계에서 지워진다.

    기사가 인용한 마크업이 조용히 없어진다.
    """
    assert clean_text("<p>이 태그는 &lt;script&gt; 다</p>") == "이 태그는 <script> 다"


def test_코드_블록이_둘_이상이면_사이_본문이_남는다():
    """비탐욕 매칭이 아니면 첫 블록부터 마지막 블록까지가 통째로 코드가 된다."""
    body, code = split_code("<pre>일</pre><p>사이</p><pre>둘</pre>")

    assert clean_text(body) == "사이"
    assert code.splitlines() == ["일", "둘"]


def test_코드_블록_안의_마크업도_씻긴다():
    """안 씻으면 `&lt;div&gt;` 가 그대로 남아 [04] 에서 후보로 올라온다."""
    _body, code = split_code("<code>&lt;div&gt;</code>")

    assert code == "<div>"


# --- 단계 2·3 링크 -------------------------------------------------------


def test_앵커_텍스트는_남고_href_는_버려진다():
    """앵커 텍스트는 사람이 고른 표현이라 후보로 값지다. URL 은 도메인·경로 조각이 잡음이 된다.

    패션 기사에서 특히 중요하다 — 앵커 텍스트가 곧 브랜드명인 경우가 잦고, URL 을 남기면
    `www`·`com`·`kr` 같은 조각이 상위 후보로 올라온다.
    """
    cleaned = clean_text('<a href="https://shop.example.com/kr/">브랜드</a> 신제품')

    assert cleaned == "브랜드 신제품"


def test_본문에_박힌_URL_은_지워진다():
    assert clean_text("<p>자세히 https://a.com/x 참고</p>") == "자세히 참고"


def test_링크만_있으면_정제_후_빈다():
    """[03 §6] 의 "링크만 있고 텍스트가 없음" 이 이 경로다. 버릴지는 필터가 정한다."""
    assert clean_text('<p><a href="https://x.com">https://x.com</a></p>') == ""


# --- 단계 2 통째로 버리는 요소 -------------------------------------------


@pytest.mark.parametrize("tag", ["script", "style", "noscript", "iframe"])
def test_내용까지_버리는_요소(tag):
    """태그만 지우면 스크립트 본문이 텍스트로 남는다."""
    cleaned = clean_text(f"<p>본문</p><{tag}>var x = 1;</{tag}>")

    assert cleaned == "본문"


def test_주석은_지워진다():
    assert clean_text("<p>본문</p><!-- 템플릿 흔적 -->") == "본문"


# --- 단계 5·6 -------------------------------------------------------------


def test_NFKC_로_전각을_접는다():
    """안 접으면 `ＡＩ` 와 `AI` 가 다른 후보가 된다."""
    assert clean_text("ＡＩ 시대") == "AI 시대"


def test_이모지와_변형_선택자를_지운다():
    """패션 매체 본문에 실제로 섞여 온다. NFKC 로는 사라지지 않는다."""
    assert clean_text("가을 신상 ️\U0001f525 출시") == "가을 신상 출시"


def test_제어문자를_지운다():
    assert clean_text("본\x00문\x07 이어짐") == "본문 이어짐"


def test_서식_문자를_지운다():
    """ZWJ·BOM 같은 `Cf` 다. 눈에 안 보이면서 토큰을 쪼갠다."""
    assert clean_text("브​랜﻿드") == "브랜드"


# --- 단계 7 공백 ----------------------------------------------------------


def test_줄바꿈은_하나까지_남는다():
    """문장 경계 정보라 [04 §6] 의 위치 가중치가 쓴다. 전부 접으면 첫 문단의 끝을 알 수 없다."""
    assert collapse_whitespace("가\n\n\n나  다   ") == "가\n나 다"


def test_블록_태그는_줄바꿈을_남기고_사라진다():
    """그냥 지우면 문단 끝 단어와 다음 문단 첫 단어가 붙어 없는 토큰이 만들어진다."""
    assert clean_text("<p>런웨이</p><p>실루엣</p>") == "런웨이\n실루엣"


def test_제목은_줄바꿈을_공백으로_접는다():
    """남으면 `contents.title` 이 화면에서 두 줄로 깨진다. 제목은 통째로 한 위치 단위다."""
    assert clean_title("<p>2026 F/W</p><p>런웨이</p>") == "2026 F/W 런웨이"


# --- 빈 입력 --------------------------------------------------------------


@pytest.mark.parametrize("raw", [None, "", "   ", "\n\n"])
def test_빈_입력은_빈_문자열이다(raw):
    """**예외를 올리지 않는다.** 회원 전용 기사에는 `body_text` 키가 아예 없다 ([02 §3])."""
    assert clean_text(raw) == ""
    assert split_code(raw) == ("", "")
