"""매체 상투 요소 제거 — 정제 단계 8 ([03 §4]). 층 1 ([09 §4]).

**입력은 2026-09-09 수집 스냅숏(fashion 373건)에서 그대로 가져온 줄이다.** 규칙을 만든
근거가 그 데이터라, 표본을 지어내면 무엇을 막으려 했는지가 테스트에서 사라진다.
"""

from __future__ import annotations

import pytest

from trendin.spark.normalize.boilerplate import strip_boilerplate


def test_관련기사_줄부터_끝까지_버린다():
    """`관련기사` 뒤는 위젯이다 — 카테고리 · 다른 기사 제목 · `2026.08.31by 원예하` 서명."""
    text = "\n".join(
        [
            "버건디 백 하나만 더해도 분위기가 확 달라져요.",
            "관련기사",
            "STYLING",
            "레드 하나만 더했을 뿐인데, 여름 코디가 달라졌습니다",
            "2026.07.05by 김가연",
        ]
    )
    assert strip_boilerplate(text) == "버건디 백 하나만 더해도 분위기가 확 달라져요."


@pytest.mark.parametrize(
    "line",
    [
        "상품 자세히 보기",
        "자세히 보기",
        "구매하러 가기",
        "보러 가기",
        "구매하기",
        "더보기",
    ],
)
def test_줄_전체가_쇼핑_앵커면_버린다(line):
    text = f"디젤디자이어 데님 쇼츠\n{line}\n헬무트 랭로우 라이즈 와이드 진"
    assert strip_boilerplate(text) == "디젤디자이어 데님 쇼츠\n헬무트 랭로우 라이즈 와이드 진"


def test_번역_고지_줄을_버린다():
    """`원문 보러 가기` 가 줄 끝에 붙어 있어 앵커 규칙으로는 안 걸린다."""
    text = (
        "선글라스로 트렌디함을 더해 마무리해보세요.\n"
        "*Cosmopolitan UK 기사를 리프트 하여 작성 되었습니다. 원문 보러 가기"
    )
    assert strip_boilerplate(text) == "선글라스로 트렌디함을 더해 마무리해보세요."


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("반클리프 아펠 주얼리 | 인스타그램 @vancleefarpels", "반클리프 아펠 주얼리"),
        ("Isabel Marant Spring/Summer 2026 | 출처 IMAXtree", "Isabel Marant Spring/Summer 2026"),
        ("부츠 컷 데님 팬츠 | 출처 게티 이미지", "부츠 컷 데님 팬츠"),
        ("몽클레르 그레노블 스노 부츠 | 사진 제공 몽클레르", "몽클레르 그레노블 스노 부츠"),
        (
            "심박수를 측정하는 스마트 워치. Photo by Justin Sullivan/게티 이미지",
            "심박수를 측정하는 스마트 워치.",
        ),
        ("백팩을 멘 사람들 스트릿 사진 출처 게티 이미지", "백팩을 멘 사람들 스트릿 사진"),
    ],
)
def test_크레딧은_꼬리만_자르고_캡션은_남긴다(line, expected):
    """**줄을 통째로 버리지 않는 이유** — 앞부분이 캡션이고 거기 브랜드명이 있다.
    `반클리프 아펠` 을 잃지 않으면서 `인스타그램` 만 없앤다."""
    assert strip_boilerplate(line) == expected


def test_본문_문장은_건드리지_않는다():
    """가장 중요한 회귀 방어 — 규칙이 본문을 먹으면 키워드가 통째로 사라진다."""
    text = (
        "밀라노 패션위크에서 오버사이즈 테일러링이 다시 중심에 섰다.\n"
        "보테가 베네타는 인트레치아토 기법을 재해석한 백을 냈다.\n"
        "올가을 가장 현실적으로 시도하기 좋은 조합이에요."
    )
    assert strip_boilerplate(text) == text


def test_상품_링크만_있던_본문은_비워진다():
    """빈 문자열이 정상 경로다 — 호출부가 요약으로 떨어뜨린다 ([03 §2])."""
    text = "상품 자세히 보기\n구매하러 가기\n관련기사\nSHOPPING"
    assert strip_boilerplate(text) == ""


@pytest.mark.parametrize("text", ["", None])
def test_빈_입력은_빈_문자열(text):
    assert strip_boilerplate(text) == ""
