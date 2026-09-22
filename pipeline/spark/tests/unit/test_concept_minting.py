"""판정이 "새 개념" 이라고 해도, 기사가 증명한 것이 있어야 사전에 넣는다."""

from __future__ import annotations

from trendin.spark.concept.minting import Evidence, MintPolicy, select

POLICY = MintPolicy(min_articles=3, min_sources=2)
KNOWN = ("vest", "sneakers")


def _proposal(normalized, english, category="person", lang="ko", surface=None):
    return (lang, normalized, surface or normalized, english, category)


def test_근거가_서면_만든다() -> None:
    mints = select(
        [_proposal("켄달 제너", "Kendall Jenner")],
        {"켄달 제너": Evidence(articles=9, sources=4)},
        KNOWN,
        POLICY,
    )
    assert [(m.canonical_name, m.category, m.normalized) for m in mints] == [
        ("Kendall Jenner", "person", "켄달 제너")
    ]


def test_한_매체에서만_나온_것은_만들지_않는다() -> None:
    """한 매체의 일회성 표기가 사전에 남으면 지우는 것은 사람 일이 된다."""
    assert select(
        [_proposal("어떤이름", "Some Name")],
        {"어떤이름": Evidence(articles=9, sources=1)},
        KNOWN,
        POLICY,
    ) == ()


def test_기사가_모자라면_만들지_않는다() -> None:
    assert select(
        [_proposal("어떤이름", "Some Name")],
        {"어떤이름": Evidence(articles=2, sources=3)},
        KNOWN,
        POLICY,
    ) == ()


def test_근거를_모르면_만들지_않는다() -> None:
    assert select([_proposal("어떤이름", "Some Name")], {}, KNOWN, POLICY) == ()


def test_세지_않을_분류는_만들지_않는다() -> None:
    """`generic` · `media` 는 순위에 올릴 대상이 아니라 개념으로 만들 것도 아니다."""
    evidence = {"요즘": Evidence(9, 4), "vogue": Evidence(9, 4)}
    assert select(
        [_proposal("요즘", "these days", "generic"), _proposal("vogue", "Vogue", "media")],
        evidence, KNOWN, POLICY,
    ) == ()


def test_이미_사전에_있는_이름은_만들지_않는다() -> None:
    """그건 새 개념이 아니라 연결해야 할 것이다. 대소문자와 단복수 흔들림까지 본다."""
    evidence = {"조끼": Evidence(9, 4), "스니커즈": Evidence(9, 4), "운동화": Evidence(9, 4)}
    assert select(
        [
            _proposal("조끼", "vest", "apparel"),
            _proposal("스니커즈", "Sneakers", "footwear"),
            _proposal("운동화", "sneaker", "footwear"),
        ],
        evidence, KNOWN, POLICY,
    ) == ()


def test_한_회차에_같은_이름을_두_번_만들지_않는다() -> None:
    """`슈즈` 와 `신발` 이 같은 영어 이름으로 오면 개념을 둘 만들 것이 아니다."""
    evidence = {"슈즈": Evidence(9, 4), "신발": Evidence(9, 4)}
    mints = select(
        [
            _proposal("슈즈", "dress shoes", "footwear"),
            _proposal("신발", "Dress Shoes", "footwear"),
        ],
        evidence, KNOWN, POLICY,
    )
    assert [m.normalized for m in mints] == ["슈즈"]


def test_표기가_같은_말이면_거기_쓰인_대소문자를_쓴다() -> None:
    """모델이 회차마다 `Zendaya` 와 `zendaya` 를 섞어 돌려준다. 화면에 보이는 이름이다."""
    mints = select(
        [_proposal("zendaya", "zendaya", surface="Zendaya")],
        {"zendaya": Evidence(9, 4)},
        KNOWN,
        POLICY,
    )
    assert [m.canonical_name for m in mints] == ["Zendaya"]


def test_표기가_다른_말이면_모델이_준_이름을_쓴다() -> None:
    mints = select(
        [_proposal("켄달 제너", "Kendall Jenner")],
        {"켄달 제너": Evidence(9, 4)},
        KNOWN,
        POLICY,
    )
    assert [m.canonical_name for m in mints] == ["Kendall Jenner"]
