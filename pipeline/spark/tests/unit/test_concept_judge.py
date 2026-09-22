"""LLM 질문 만들기와 답 읽기 — 부르지 않고 시험한다.

여기 시험이 지키는 것은 둘이다. **답이 이상해도 조용히 넘어가지 않는 것**, 그리고 **받은
영어 이름으로 사전을 찾을 때 중복 개념을 만들지 않는 것**이다.
"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

import trendin.spark.io as io
from trendin.spark.concept.auto_link import Link, apply_links, select_links
from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.judge import (
    DECISION_CHECK,
    DECISION_LINK,
    DECISION_NEW,
    NameIndex,
    Question,
    Verdict,
    batches,
    name_variants,
    parse,
    user_prompt,
)

BATCH = [
    Question(index=1, lang="ko", normalized="빈티지", article_count=25),
    Question(index=2, lang="ko", normalized="제니", article_count=11),
]

CONCEPTS = (
    Concept(concept_id=1, canonical_name="sneakers", category="footwear"),
    Concept(concept_id=2, canonical_name="polo shirt", category="apparel"),
    Concept(concept_id=3, canonical_name="Christian Dior", category="designer"),
)
EXPRESSIONS = (
    Expression(expression_id=11, concept_id=1, lang="en", normalized="sneakers"),
    Expression(expression_id=12, concept_id=1, lang="ko", normalized="스니커즈"),
    Expression(expression_id=21, concept_id=2, lang="en", normalized="polo shirt"),
    Expression(expression_id=31, concept_id=3, lang="en", normalized="christian dior"),
)


def index() -> NameIndex:
    return NameIndex(Dictionary(CONCEPTS, EXPRESSIONS))


def answer(rows: list[dict]) -> str:
    return json.dumps({"r": rows}, ensure_ascii=False)


def test_물음에_표기만_싣는다() -> None:
    # 문맥도 후보도 넣지 않는다. 토큰이 거기서 제일 많이 샌다.
    prompt = user_prompt(BATCH)
    assert "빈티지" in prompt and "제니" in prompt
    assert len(prompt) < 120


def test_답을_표기에_되돌려_붙인다() -> None:
    verdicts, problems = parse(
        answer(
            [{"i": 1, "en": "vintage", "cat": "style"}, {"i": 2, "en": "Jennie", "cat": "person"}]
        ),
        BATCH,
    )
    assert problems == []
    assert [(v.normalized, v.english_name, v.category) for v in verdicts] == [
        ("빈티지", "vintage", "style"),
        ("제니", "Jennie", "person"),
    ]


def test_영어_이름_자리에_generic_이_오면_버린다() -> None:
    # 프롬프트 v1 에서 38건이 이랬다. 받아들이면 서른여덟 개가 한 개념으로 뭉친다.
    verdicts, problems = parse(answer([{"i": 1, "en": "generic", "cat": "generic"}]), BATCH[:1])
    assert verdicts == []
    assert any("generic 이 왔다" in p for p in problems)


def test_분류와_같은_이름은_막지_않는다() -> None:
    # `액세서리` 의 영어 이름은 accessory 다. 분류 이름과 겹칠 뿐 옳은 답이다.
    verdicts, problems = parse(answer([{"i": 1, "en": "accessory", "cat": "accessory"}]), BATCH[:1])
    assert problems == []
    assert verdicts[0].english_name == "accessory"


def test_이름이_같아도_분류가_다르면_잇지_않는다() -> None:
    # `에스파 윈터`(사람)와 `겨울`(계절)이 둘 다 Winter 로 온다.
    wide = NameIndex(
        Dictionary(
            (*CONCEPTS, Concept(concept_id=4, canonical_name="winter", category="generic")),
            (
                *EXPRESSIONS,
                Expression(expression_id=41, concept_id=4, lang="en", normalized="winter"),
            ),
        )
    )
    assert wide.resolve("Winter", "generic").decision == DECISION_LINK
    assert wide.resolve("Winter", "person").decision == DECISION_CHECK


def test_빠뜨린_항목을_알린다() -> None:
    _, problems = parse(answer([{"i": 1, "en": "vintage", "cat": "style"}]), BATCH)
    assert any("제니" in p for p in problems)


def test_모르는_분류는_버린다() -> None:
    verdicts, problems = parse(answer([{"i": 1, "en": "vintage", "cat": "mood"}]), BATCH[:1])
    assert verdicts == []
    assert any("모르는 분류" in p for p in problems)


def test_JSON_이_아니면_배치_전체를_문제로_올린다() -> None:
    verdicts, problems = parse("미안하지만 못 하겠다", BATCH)
    assert verdicts == []
    assert problems


def test_코드_울타리를_벗긴다() -> None:
    fenced = '```json\n{"r":[{"i":1,"en":"vintage","cat":"style"}]}\n```'
    verdicts, _ = parse(fenced, BATCH[:1])
    assert verdicts[0].english_name == "vintage"


def test_같은_이름이면_기존_개념에_잇는다() -> None:
    assert index().resolve("sneakers").decision == DECISION_LINK


def test_단수_복수가_갈리지_않는다() -> None:
    # 모델이 `sneaker` 라고 답해도 `sneakers` 개념을 찾아야 한다.
    resolution = index().resolve("sneaker")
    assert resolution.decision == DECISION_LINK
    assert resolution.concept_ids == (1,)


def test_아주_닮은_이름은_사람이_본다() -> None:
    # `polo` 는 `polo shirt` 일 수도 있고 브랜드일 수도 있다. 멋대로 만들지 않는다.
    resolution = index().resolve("polo shirts")
    assert resolution.decision in (DECISION_LINK, DECISION_CHECK)


def test_닮은_것도_없으면_새로_만든다() -> None:
    resolution = index().resolve("balletcore")
    assert resolution.decision == DECISION_NEW
    assert resolution.near == ()


def test_대소문자와_구두점은_무시한다() -> None:
    assert index().resolve("Christian Dior.").decision == DECISION_LINK


def test_복수형_후보() -> None:
    assert "shoe" in name_variants("shoes")
    assert "flats" in name_variants("flat")


def test_배치를_크기대로_나눈다() -> None:
    questions = [Question(i, "ko", f"말{i}", 1) for i in range(1, 6)]
    assert [len(g) for g in batches(questions, 2)] == [2, 2, 1]


def test_자동연결은_정확한_영어이름과_분류가_유일할때만() -> None:
    names = NameIndex(
        Dictionary(
            (*CONCEPTS, Concept(4, "Winter", "generic"), Concept(5, "Winter", "person")),
            EXPRESSIONS,
        )
    )
    verdicts = [
        Verdict("ja", "スニーカー", "sneakers", "footwear"),
        Verdict("ja", "ポロ", "polo shirts", "apparel"),  # 단복수 변형은 검수
        Verdict("ja", "ウィンター", "Winter", "person"),  # 이름 중복
        Verdict("ja", "スニーカーの人", "sneakers", "person"),
        Verdict("ja", "夏", "summer", "generic"),
    ]
    contexts = {(v.lang, v.normalized): f"{v.normalized} が話題だ" for v in verdicts}
    links = select_links(verdicts, names, contexts)
    assert [(link.verdict.normalized, link.concept_id) for link in links] == [
        ("スニーカー", 1)
    ]


def test_문맥이_표기_한_낱말뿐이면_정확_일치라도_잇지_않는다() -> None:
    """`Coach` 는 사전에 브랜드로만 있지만 감독이기도 하다. 가릴 근거가 없으면 사람에게 넘긴다."""
    names = NameIndex(Dictionary(CONCEPTS, EXPRESSIONS))
    verdicts = [Verdict("ja", "スニーカー", "sneakers", "footwear")]

    assert select_links(verdicts, names, {("ja", "スニーカー"): "スニーカー"}) == ()
    assert select_links(verdicts, names, {("ja", "スニーカー"): "  "}) == ()
    assert select_links(verdicts, names, {}) == ()
    assert len(select_links(verdicts, names, {("ja", "スニーカー"): "白いスニーカーが流行"})) == 1


def test_자동연결은_한번만_쓰고_결정과_버전을_남긴다() -> None:
    class Cursor:
        def __init__(self) -> None:
            self.status = "PENDING"
            self.result = None
            self.writes: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params=None) -> None:
            if "SELECT coalesce(max(version)" in sql:
                self.result = (4,)
            elif "SELECT status, surface_sample" in sql:
                self.result = (self.status, "スニーカー")
            elif "SELECT 1 FROM" in sql:
                self.result = None
            else:
                self.result = None
                if sql.startswith(("INSERT", "UPDATE")):
                    self.writes.append(sql)
                if "UPDATE pl_unmapped_expression" in sql:
                    self.status = "RESOLVED"

        def fetchone(self):
            return self.result

    class Connection:
        def __init__(self, cursor) -> None:
            self._cursor = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cursor(self):
            return self._cursor

    cursor = Cursor()
    modules = {
        "trendin.spark.io.jdbc": SimpleNamespace(connection=lambda _: Connection(cursor)),
        "trendin.spark.io.concepts": SimpleNamespace(
            DECISION="pl_mapping_decision", EXPRESSION="pl_concept_expression",
            UNMAPPED="pl_unmapped_expression", VERSION="pl_dictionary_version",
        ),
    }
    link = Link(Verdict("ja", "スニーカー", "sneakers", "footwear"), 1)
    # `from trendin.spark.io import jdbc` 는 이미 로드된 패키지 속성을 우선 보므로
    # sys.modules 와 패키지 속성을 함께 바꿔 실제 DB 연결을 막는다.
    with patch.dict(sys.modules, modules), patch.object(
        io, "jdbc", modules["trendin.spark.io.jdbc"], create=True
    ):
        assert apply_links(None, (link,), model="test", prompt_version="name-v2") == 1
        assert apply_links(None, (link,), model="test", prompt_version="name-v2") == 0
    assert len(cursor.writes) == 4  # 표현, 미등록 상태, 결정 이력, 사전 버전
