"""기사 하나 → 개념 행. 기사·개념 한 쌍에 한 행, 모호하면 문맥 규칙, 안 갈리면 유보."""

from __future__ import annotations

from trendin.spark.concept.dictionary import Concept, Dictionary, Expression
from trendin.spark.concept.mapping import (
    METHOD_CONTEXT,
    METHOD_DICT,
    Keyword,
    disambiguate,
    map_article,
)

BOOTS = Concept(1201, "boots", "footwear")
ANKLE = Concept(1210, "ankle boots", "footwear", parent_id=1201)
BOTTEGA = Concept(3007, "Bottega Veneta", "brand")
COAT = Concept(1305, "coat", "apparel")
COURT = Concept(9001, "court", "sports")
FEELING = Concept(7001, "feeling", "generic", countable=False)

DICTIONARY = Dictionary(
    concepts=[BOOTS, ANKLE, BOTTEGA, COAT, COURT, FEELING],
    expressions=[
        Expression(1, 1201, "ko", "부츠"),
        Expression(2, 1201, "en", "boots"),
        Expression(3, 1210, "ko", "앵클부츠"),
        Expression(4, 3007, "en", "bottega veneta"),
        Expression(5, 1305, "ko", "코트", ambiguous=True),
        Expression(6, 9001, "ko", "코트", ambiguous=True),
        Expression(7, 7001, "ko", "느낌"),
    ],
)


def rows_by_concept(result):
    return {row.concept_id: row for row in result.rows}


def test_사전에_있으면_붙고_없으면_미등록이다():
    result = map_article(
        article_id=10,
        article_lang="ko",
        keywords=[
            Keyword("부츠"),
            Keyword("Bottega Veneta"),
            Keyword("발레코어", context="발레코어 룩이 다시"),
        ],
        dictionary=DICTIONARY,
    )
    rows = rows_by_concept(result)
    assert set(rows) == {1201, 3007}
    assert rows[1201].method == METHOD_DICT
    assert rows[3007].expression_ids == (4,)  # 한국 기사 안의 라틴 표기도 붙는다
    assert [(u.lang, u.normalized, u.context) for u in result.unmapped] == [
        ("ko", "발레코어", "발레코어 룩이 다시")
    ]
    # 라틴 표기의 입력 언어는 la 여도 사전의 en 표현에 붙는다. 검수 대기 정리는
    # 사전 표현의 언어가 아니라 이 입력 키로 해야 한다.
    assert result.resolved_keys == (("ko", "부츠"), ("la", "bottega veneta"))
    assert result.deferred == ()


def test_같은_개념의_표현이_둘이어도_행은_하나다():
    result = map_article(10, "ko", [Keyword("부츠"), Keyword("boots"), Keyword("부츠")], DICTIONARY)
    assert len(result.rows) == 1
    assert result.rows[0].expression_ids == (1, 2)


def test_상위와_하위는_따로_행이_난다():
    # 부츠(상위)와 앵클부츠(하위)가 같이 나오면 두 행이다. 상위 묶음 집계에서 한 번으로 접는 것은
    # 랭킹의 일이다 — 여기서 접으면 하위 집계가 사라진다.
    result = map_article(10, "ko", [Keyword("부츠"), Keyword("앵클부츠")], DICTIONARY)
    assert set(rows_by_concept(result)) == {1201, 1210}


def test_모호한_표기는_기사의_다른_개념_분류로_가른다():
    # 코트 = 외투(apparel) | 경기장(sports). 기사에 신발이 붙어 있으면 패션 쪽 후보가 하나라 외투다.
    result = map_article(10, "ko", [Keyword("부츠"), Keyword("코트")], DICTIONARY)
    rows = rows_by_concept(result)
    assert 1305 in rows and 9001 not in rows
    assert rows[1305].method == METHOD_CONTEXT
    assert result.deferred == ()


def test_가를_근거가_없으면_유보한다():
    # 기사에 다른 개념이 하나도 없다. 세지 않고 기록만 남긴다.
    result = map_article(10, "ko", [Keyword("코트")], DICTIONARY)
    assert result.rows == ()
    assert result.resolved_keys == ()
    assert [(d.normalized, d.concept_ids) for d in result.deferred] == [("코트", (1305, 9001))]


def test_일반_단어도_사전에_있으면_붙는다_세는_것은_랭킹이_거른다():
    result = map_article(10, "ko", [Keyword("느낌")], DICTIONARY)
    assert [r.concept_id for r in result.rows] == [7001]
    assert DICTIONARY.concept(7001).countable is False
    assert result.unmapped == ()  # 매일 미등록으로 다시 올라오지 않는다


def test_빈_표기는_건너뛴다():
    result = map_article(10, "ko", [Keyword(""), Keyword("  ,, ")], DICTIONARY)
    assert result.rows == () and result.unmapped == ()


def test_disambiguate_같은_분류가_둘이면_못_가른다():
    hits = DICTIONARY.lookup("ko", "코트")
    # 기사에 apparel 과 sports 가 둘 다 붙어 있으면 어느 쪽도 못 고른다.
    assert disambiguate(hits, {1305: COAT, 9001: COURT}) is None
