"""구간 → 후보 묶음 (`extract/document.py`). 층 1 — UDF 본체를 Spark 없이 본다.

**모델을 부르지 않는다.** 추론은 `extract/batch.py` 가 파티션 단위로 하고, 이 파일은 그
결과를 받는다. 그래서 여기서는 구간을 손으로 만들어 넣는다 — 후처리·합치기·필터가 무엇을
하는지가 이 테스트의 관심사다.
"""

from __future__ import annotations

from trendin.spark.extract import filters
from trendin.spark.extract.document import ExtractionOptions, document_text, extract_document
from trendin.spark.extract.entities import Span
from trendin.spark.normalize.lang import EN, KO, MIXED

OPTIONS = ExtractionOptions()


def span(surface: str, *, label: str = "브랜드", score: float = 0.9, start: int = 0) -> Span:
    return Span(surface=surface, label=label, score=score, start=start, end=start + len(surface))


def by_key(extraction):
    return {item.key: item for item in extraction.candidates}


def test_본문_없는_문서는_제목만으로_돈다():
    """`hn` · `members_only` — [03 §2] 가 살려 보낸 이유."""
    title = "Chanel Cruise 2027"
    result = extract_document(title, None, EN, [span("Chanel")], options=OPTIONS)

    assert set(by_key(result)) == {"chanel"}
    assert result.doc_len == len(title)
    # 제목만 있는 문서이므로 모든 출현이 제목 출현이다.
    assert all(item.tf_title == item.tf for item in result.candidates)


def test_제목과_본문을_잇고_시작_위치로_제목을_가른다():
    text, title_len = document_text("Chanel", "Prada 와 Chanel 이 나왔다")
    assert text == "Chanel\nPrada 와 Chanel 이 나왔다" and title_len == 6

    result = extract_document(
        "Chanel",
        "Prada 와 Chanel 이 나왔다",
        MIXED,
        [span("Chanel", start=0), span("Prada", start=7), span("Chanel", start=15)],
        options=OPTIONS,
    )
    assert by_key(result)["chanel"].tf_title == 1
    assert by_key(result)["prada"].tf_title == 0


def test_문서_안에서_비교키로_합친다():
    spans = [
        span("Chanel", score=0.9),
        span("chanel", score=0.7, start=20),
        span("CHANEL", score=0.8, start=40),
    ]
    result = extract_document("t", "b", EN, spans, options=OPTIONS)
    item = by_key(result)["chanel"]

    assert item.tf == 3
    # **최빈 표기가 아니라 최고 점수 표기다** — 모델이 확신한 자리가 경계도 제대로 잡힌 자리다.
    assert item.surface == "Chanel"


def test_반복은_점수를_올리되_1_을_넘지_않는다():
    once = extract_document("t", "b", EN, [span("Chanel", score=0.5)], options=OPTIONS)
    twice = extract_document(
        "t", "b", EN, [span("Chanel", score=0.5), span("Chanel", score=0.5, start=9)],
        options=OPTIONS,
    )
    assert by_key(once)["chanel"].score == 0.5
    assert by_key(twice)["chanel"].score == 0.55

    many = [span("Chanel", score=0.95, start=i * 9) for i in range(8)]
    capped = extract_document("t", "b", EN, many, options=OPTIONS)
    assert by_key(capped)["chanel"].score == 1.0


def test_유형과_고유명사_표시가_실린다():
    spans = [span("Chanel", label="브랜드"), span("silk", label="소재", start=10)]
    result = extract_document("t", "b", EN, spans, options=OPTIONS)

    assert by_key(result)["chanel"].entity_type == "브랜드"
    assert by_key(result)["chanel"].is_proper is True
    # 소재는 고유명사가 아니다 — `entities.PROPER_LABELS` 가 정한다.
    assert by_key(result)["silk"].is_proper is False


def test_한국어_조사가_떨어진다():
    result = extract_document(
        "제니가 입은 데님 팬츠가 화제다", None, KO,
        [span("제니가"), span("데님 팬츠가", start=7)],
        options=OPTIONS,
    )
    assert set(by_key(result)) == {"제니", "데님 팬츠"}


def test_문서_안_필터가_버린_것을_사유별로_센다():
    spans = [span("29,000원"), span("A", start=9), span("Chanel", start=12)]
    result = extract_document("t", "b", EN, spans, options=OPTIONS)

    assert set(by_key(result)) == {"chanel"}
    assert result.dropped[filters.SHAPE] == 2


def test_라벨_제한에_걸린_구간을_센다():
    from trendin.spark.normalize.lang import JA

    spans = [span("ケンゾー", label="브랜드"), span("スウェット", label="의류 품목", start=6)]
    result = extract_document("t", "b", JA, spans, options=OPTIONS)

    assert set(by_key(result)) == {"ケンゾー"}
    assert result.dropped[filters.LABEL] == 1


def test_약어_전개형_쌍을_문서당_한_번만():
    body = "Model Context Protocol (MCP) 은 표준이다. Model Context Protocol (MCP) 을 쓴다."
    result = extract_document("t", body, EN, [], options=OPTIONS)

    assert len(result.abbreviations) == 1
    assert result.abbreviations[0].abbreviation == "MCP"


def test_순서가_결정적이다():
    """등장 순서를 유지한다 — 스냅샷이 서려면 필요하다 ([04 §9])."""
    spans = [span("Prada"), span("Chanel", start=6), span("Gucci", start=13)]
    result = extract_document("t", "b", EN, spans, options=OPTIONS)
    assert [item.key for item in result.candidates] == ["prada", "chanel", "gucci"]


def test_빈_문서():
    result = extract_document(None, None, None, [], options=OPTIONS)
    assert result.candidates == () and result.doc_len == 0 and result.dropped == {}
