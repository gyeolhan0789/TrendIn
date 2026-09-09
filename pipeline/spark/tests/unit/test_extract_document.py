"""문서 하나 → 후보 묶음 (`extract/document.py`). 층 1 — UDF 본체를 Spark 없이 본다."""

from __future__ import annotations

from trendin.spark.extract import filters
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.document import ExtractionOptions, extract_document
from trendin.spark.extract.lexicon import Lexicon
from trendin.spark.normalize.lang import EN, MIXED

LEXICON = Lexicon.of(stopwords=["the", "is", "for", "and", "of", "이번"], noise=["tmp"])
OPTIONS = ExtractionOptions(lexicon=LEXICON)


def by_key(extraction):
    return {item.key: item for item in extraction.candidates}


def test_본문_없는_문서는_제목만으로_돈다():
    """`hn` · `members_only` — [03 §2] 가 살려 보낸 이유."""
    result = extract_document("Postgres 16 and the new agentic workflow", None, EN, options=OPTIONS)

    keys = set(by_key(result))
    assert {"postgres", "postgres 16", "agentic workflow"} <= keys
    assert all(item.tf_title == item.tf for item in result.candidates)
    assert result.doc_len == 7


def test_문서_안에서_비교키로_합친다():
    body = "The agentic workflow is here. Agentic Workflow again, agentic workflow!"
    result = extract_document("Agentic workflow", body, EN, options=OPTIONS)
    item = by_key(result)["agentic workflow"]

    assert item.tf == 4 and item.tf_title == 1
    assert item.ntokens == 2
    # 문서 안 최다 표기. `agentic workflow` 2회 vs `Agentic workflow` · `Agentic Workflow` 1회.
    assert item.surface == "agentic workflow"


def test_부모_관계를_합친다():
    result = extract_document("new agentic workflow", "agentic workflow tools", EN, options=OPTIONS)
    assert by_key(result)["workflow"].parents == (
        "agentic workflow",
        "agentic workflow tools",
        "new agentic workflow",
        "workflow tools",
    )


def test_문서_안_필터가_버린_것을_사유별로_센다():
    result = extract_document("tmp", "a 29,000원 tmp thing", EN, options=OPTIONS)

    assert result.dropped[filters.NOISE] == 1  # tmp — 제목·본문 합쳐 비교키 하나
    assert (
        result.dropped[filters.SHAPE] == 1
    )  # 29,000원 (a · 2026 같은 것은 후보가 되기 전에 빠진다)
    assert "tmp" not in by_key(result) and "thing" in by_key(result)


def test_약어_전개형_쌍을_문서당_한_번만():
    body = "Model Context Protocol (MCP) ... again Model Context Protocol (MCP)."
    result = extract_document("MCP", body, EN, options=OPTIONS)

    assert len(result.abbreviations) == 1
    assert result.abbreviations[0].expansion_key == "model context protocol"


def test_도메인_옵션이_토크나이저까지_간다():
    options = ExtractionOptions(
        lexicon=LEXICON, tokenize=tk.TokenizeOptions(code_identifiers=False)
    )
    result = extract_document("next.config", None, EN, options=options)
    assert "next.config" not in by_key(result) and "next config" in by_key(result)


def test_한국어_혼합_문서():
    body = (
        "보테가 베네타가 2026 컬렉션을 공개했다. Bottega Veneta 의 인트레치아토 기법을 재해석했다."
    )
    result = extract_document("보테가 베네타 컬렉션", body, MIXED, options=OPTIONS)
    keys = by_key(result)

    assert "보테가 베네타" in keys and "bottega veneta" in keys and "인트레치아토 기법" in keys
    assert keys["컬렉션"].tf == 2 and keys["컬렉션"].tf_title == 1


def test_순서가_결정적이다():
    """스냅샷 테스트([04 §9])가 서려면 같은 입력이 같은 순서로 나와야 한다."""
    body = "ballet sneakers and ballet flats"
    first = extract_document("ballet", body, EN, options=OPTIONS).as_row()
    second = extract_document("ballet", body, EN, options=OPTIONS).as_row()
    assert first == second
    assert [c["key"] for c in first["candidates"]][:3] == ["ballet", "sneakers", "ballet sneakers"]


def test_빈_문서():
    result = extract_document("", "", EN, options=OPTIONS)
    assert result.candidates == () and result.doc_len == 0 and result.dropped == {}
