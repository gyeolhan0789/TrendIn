"""덩이째 묻는 판정의 프롬프트와 답 읽기 (`concept/cluster_judge.py`, S15P21A102-386)."""

from __future__ import annotations

import json

from trendin.spark.concept.cluster_judge import (
    CONTEXTS_PER_MEMBER,
    Cluster,
    Judgement,
    Member,
    batches,
    mentions,
    merged_pairs,
    messages,
    parse,
    user_prompt,
)

VOGUE = Cluster(
    members=(
        Member(
            "vogue world", "Vogue World", "컬렉션 또는 행사", ("Vogue World returns to Milan.",)
        ),
        Member("vogue world 2026", "Vogue World 2026"),
        Member("vogue world milano", "Vogue World: Milano"),
    ),
    pairs=(
        ("vogue world", "vogue world 2026", 3),
        ("vogue world", "vogue world milano", 0),
    ),
)
DRESS = Cluster(
    members=(Member("mini dress", "mini dress"), Member("black mini dress", "black mini dress")),
    pairs=(("black mini dress", "mini dress", 0),),
)


def prompt(clusters: list[Cluster]) -> dict:
    return json.loads(user_prompt(clusters))


# --- 프롬프트 -------------------------------------------------------------


def test_덩이마다_번호를_달고_표기와_쌍을_싣는다():
    (cluster,) = prompt([VOGUE])["clusters"]
    assert cluster["n"] == 1
    assert cluster["items"][0] == {
        "i": 1,
        "w": "Vogue World",
        "k": "컬렉션 또는 행사",
        "c": ["Vogue World returns to Milan."],
    }
    assert cluster["items"][1] == {"i": 2, "w": "Vogue World 2026"}
    assert cluster["p"] == [[1, 1, 2, 3], [2, 1, 3, 0]]


def test_여러_덩이를_한_요청에_담는다():
    clusters = prompt([VOGUE, DRESS])["clusters"]
    assert [c["n"] for c in clusters] == [1, 2]
    assert clusters[1]["p"] == [[1, 2, 1, 0]]


def test_표기가_들어_있지_않은_문장은_싣지_않는다():
    """옛 문맥 칸에는 기사 제목이 들어 있다 — 표기가 없는 제목은 엉뚱한 쪽으로 끈다."""
    member = Member(
        "vogue world",
        "Vogue World",
        None,
        ("Wunmi Mosaku Is British Vogue's October Cover Star", "Vogue World", "At Vogue World: 1"),
    )
    (item,) = prompt([Cluster((member,), ())])["clusters"][0]["items"]
    assert item["c"] == ["At Vogue World: 1"]


def test_문장은_표기당_상한까지만_싣는다():
    member = Member("lfw", "LFW", None, tuple(f"LFW day {n}" for n in range(5)))
    (item,) = prompt([Cluster((member,), ())])["clusters"][0]["items"]
    assert len(item["c"]) == CONTEXTS_PER_MEMBER


def test_문장부호와_대소문자는_무시하고_찾는다():
    assert mentions("the vogue world milano show", "Vogue World: Milano")
    assert not mentions("British Vogue's cover", "Vogue World")


def test_지시문이_먼저_온다():
    first, second = messages([VOGUE])
    assert first["role"] == "system" and second["role"] == "user"


def test_정해진_크기로_나눈다():
    assert [len(b) for b in batches([VOGUE] * 7, size=5)] == [5, 2]


# --- 답 읽기 --------------------------------------------------------------


def test_쌍마다_관계를_읽는다():
    content = json.dumps(
        {
            "r": [
                {"n": 1, "p": 1, "rel": "series"},
                {"n": 1, "p": 2, "rel": "series"},
                {"n": 2, "p": 1, "rel": "narrower"},
            ]
        }
    )
    (vogue, dress), problems = parse(content, [VOGUE, DRESS])
    assert problems == []
    assert vogue.relations == {
        ("vogue world", "vogue world 2026"): "series",
        ("vogue world", "vogue world milano"): "series",
    }
    assert dress.relations == {("black mini dress", "mini dress"): "narrower"}


def test_코드_울타리를_벗긴다():
    (judgement,), problems = parse('```json\n{"r":[{"n":1,"p":1,"rel":"narrower"}]}\n```', [DRESS])
    assert problems == [] and judgement is not None


def test_어긋난_덩이만_버리고_나머지는_살린다():
    """쌍이 하나 빠진 덩이는 묶음이 달라지므로 버린다. 다른 덩이는 멀쩡하다."""
    content = '{"r":[{"n":1,"p":1,"rel":"series"},{"n":2,"p":1,"rel":"narrower"}]}'
    (vogue, dress), problems = parse(content, [VOGUE, DRESS])
    assert vogue is None
    assert dress is not None
    assert any("답이 없는 쌍" in p for p in problems)


def test_모르는_관계나_번호는_그_덩이를_버린다():
    for content, word in [
        ('{"r":[{"n":1,"p":1,"rel":"maybe"}]}', "모르는 관계"),
        ('{"r":[{"n":1,"p":9,"rel":"same"},{"n":1,"p":1,"rel":"same"}]}', "모르는 쌍"),
    ]:
        (judgement,), problems = parse(content, [DRESS])
        assert judgement is None
        assert any(word in p for p in problems), (content, problems)


def test_같은_쌍에_다른_답이면_버린다():
    content = '{"r":[{"n":1,"p":1,"rel":"same"},{"n":1,"p":1,"rel":"narrower"}]}'
    (judgement,), problems = parse(content, [DRESS])
    assert judgement is None and any("두 번" in p for p in problems)


def test_JSON_이_아니면_전부_버린다():
    judgements, problems = parse("not json", [VOGUE, DRESS])
    assert judgements == [None, None] and problems


# --- 묶음 -----------------------------------------------------------------


def test_합치는_쌍을_이어_묶음을_만든다():
    """후보가 아니었던 `2026` ↔ `milano` 도 둘 다 `vogue world` 와 이어지면 한 줄이다."""
    judgement = Judgement(
        {
            ("vogue world", "vogue world 2026"): "series",
            ("vogue world", "vogue world milano"): "same",
        }
    )
    assert merged_pairs(judgement) == {
        ("vogue world", "vogue world 2026"): "series",
        ("vogue world", "vogue world milano"): "series",
        ("vogue world 2026", "vogue world milano"): "series",
    }


def test_합치지_않는_관계는_묶지_않는다():
    judgement = Judgement({("black mini dress", "mini dress"): "narrower"})
    assert merged_pairs(judgement) == {}
