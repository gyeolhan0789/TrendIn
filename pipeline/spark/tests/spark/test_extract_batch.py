"""후보 추출 배선 ([09 §4] 층 2).

층 1 은 토큰화·후보·수식이 맞는지만 본다. 여기서 보는 것은 **배선** — UDF 가 후보를 펴는지,
DF 필터가 코퍼스 비율로 도는지, 대표 표기가 코퍼스에서 뽑히는지, 문서 안 정규화·순위·선별이
[04 §7] 대로 나오는지, 적재 프레임의 칸이 `io/candidates.py` 의 컬럼과 같은지다.

**MinIO · PostgreSQL 은 쓰지 않는다.** 입력은 인메모리 DataFrame(`curated` 의 칸만 흉내), 출력은
프레임을 `collect()` 해서 본다.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib

from trendin.spark.extract import batch, filters, source
from trendin.spark.extract import tokenize as tk
from trendin.spark.extract.document import ExtractionOptions
from trendin.spark.extract.lexicon import Lexicon
from trendin.spark.extract.thresholds import DomainOptions, ExtractThresholds
from trendin.spark.io import candidates as candidates_io
from trendin.spark.normalize.lang import EN, KO

RUN = "20260909T000000"

LEXICON = Lexicon.of(
    stopwords=["the", "is", "and", "of", "for", "with", "a", "to", "in", "이번", "시즌"],
)

THRESHOLDS = ExtractThresholds(
    corpus_window_days=30,
    ngram_max=3,
    min_chars=2,
    max_chars=40,
    df_min_ratio=0.0,  # 작은 코퍼스 — 하한은 최소 1 이다
    df_max_ratio=1.0,  # 문서 둘짜리 코퍼스에서 둘 다에 나오는 것이 "너무 흔한" 게 아니다
    bm25_k1=1.2,
    bm25_b=0.75,
    weight_c_value=0.3,
    weight_bm25=0.4,
    weight_title=0.3,
    per_document_top_k=3,
    score_floor=0.2,
)


def h(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def doc(
    url: str,
    title: str,
    body: str | None,
    *,
    lang=EN,
    source_id="hn",
    domain="dev",
    author=None,
    day="2026-09-03",
    dup_of=None,
    run=RUN,
):
    published = dt.datetime.fromisoformat(f"{day}T09:00:00+00:00")
    return {
        "url_hash": bytearray(h(url)),
        "source_id": source_id,
        "domain": domain,
        "title": title,
        "body": body,
        "lang": lang,
        "author": author,
        "published_at": published,
        "published_date": dt.date.fromisoformat(day),
        "dup_of": None if dup_of is None else bytearray(h(dup_of)),
        "ingest_run_id": run,
    }


SCHEMA = (
    "url_hash binary, source_id string, domain string, title string, body string, lang string, "
    "author string, published_at timestamp, published_date date, dup_of binary, "
    "ingest_run_id string"
)


def frame(spark, docs):
    return spark.createDataFrame([tuple(d[k] for k in source.COLUMNS) for d in docs], SCHEMA)


def run_batch(spark, docs, *, targets=None, domain="dev", options=None, domain_options=None):
    corpus = frame(spark, docs)
    target = corpus if targets is None else frame(spark, targets)
    return batch.extract_batch(
        targets=target,
        corpus=corpus,
        domain=domain,
        thresholds=THRESHOLDS,
        options=options or ExtractionOptions(lexicon=LEXICON),
        domain_options=domain_options or DomainOptions(),
        extract_run_id=RUN,
    )


DEV_DOCS = [
    doc(
        "u1",
        "Agentic workflow with Postgres 16",
        "The agentic workflow is changing how teams ship. Postgres 16 helps.",
    ),
    doc(
        "u2",
        "Vibe coding and agentic workflow",
        "Vibe coding is the new agentic workflow for solo developers.",
    ),
    doc(
        "u3",
        "Show HN: kubectl plugin",
        "A kubectl plugin for agentic workflow automation and vibe coding.",
    ),
    doc("u4", "Rust 1.80 released", None),  # 본문 없는 hn 문서
]


# --- 배선 ---------------------------------------------------------------------


def test_적재_프레임의_칸이_컬럼_정의와_같다(spark):
    result = run_batch(spark, DEV_DOCS)
    try:
        assert tuple(result.document_candidates.columns) == candidates_io.DOCUMENT_CANDIDATE_COLUMNS
        assert tuple(result.abbreviations.columns) == candidates_io.ABBREVIATION_COLUMNS
        assert tuple(result.documents.columns) == candidates_io.EXTRACTED_DOCUMENT_COLUMNS
        assert result.corpus_size == 4 and result.target_count == 4
    finally:
        result.release()


def test_문서마다_후보가_펴지고_본문_없는_문서도_돈다(spark):
    result = run_batch(spark, DEV_DOCS)
    try:
        rows = result.document_candidates.collect()
        by_doc = {}
        for row in rows:
            by_doc.setdefault(bytes(row["url_hash"]), []).append(row)

        assert set(by_doc) == {h("u1"), h("u2"), h("u3"), h("u4")}
        rust = {row["normalized_key"] for row in by_doc[h("u4")]}
        assert {"rust", "rust 1.80", "released"} <= rust
        assert all(row["in_title"] for row in by_doc[h("u4")])
        assert all(row["domain"] == "dev" and row["extract_run_id"] == RUN for row in rows)
        assert all(row["stat_date"] == dt.date(2026, 9, 3) for row in rows)
    finally:
        result.release()


def test_대표_표기는_코퍼스에서_가장_빈번한_원표기다(spark):
    """u1 제목 `Agentic workflow`, 본문들 `agentic workflow` ×4 — 소문자가 대표다 ([04 §4])."""
    result = run_batch(spark, DEV_DOCS)
    try:
        surfaces = {
            row["surface"]
            for row in result.document_candidates.where(
                "normalized_key = 'agentic workflow'"
            ).collect()
        }
        assert surfaces == {"agentic workflow"}
    finally:
        result.release()


def test_DF_는_코퍼스_전체에서_센다(spark):
    """대상이 문서 하나여도 DF 는 코퍼스 4건 기준이다 — 배치 크기에 결과가 흔들리면 안 된다."""
    result = run_batch(spark, DEV_DOCS, targets=[DEV_DOCS[0]])
    try:
        rows = {row["normalized_key"]: row for row in result.document_candidates.collect()}
        assert rows["agentic workflow"]["df"] == 3
        assert rows["postgres 16"]["df"] == 1
        assert result.target_count == 1 and result.corpus_size == 4
    finally:
        result.release()


def test_DF_상한에_걸린_후보는_사라지고_통계에_남는다(spark):
    """`agentic workflow` 는 4건 중 3건 — 상한을 50% 로 두면 탈락한다 ([04 §5] 6번)."""
    thresholds = dataclasses.replace(THRESHOLDS, df_max_ratio=0.5)
    corpus = frame(spark, DEV_DOCS)
    result = batch.extract_batch(
        targets=corpus,
        corpus=corpus,
        domain="dev",
        thresholds=thresholds,
        options=ExtractionOptions(lexicon=LEXICON),
        domain_options=DomainOptions(),
        extract_run_id=RUN,
    )
    try:
        keys = {row["normalized_key"] for row in result.document_candidates.collect()}
        assert "agentic workflow" not in keys and "agentic" not in keys
        assert "postgres 16" in keys
        stats = {(s.metric, s.dimension): s.value for s in result.stats}
        assert stats[(batch.DROPPED, f"dev/{filters.DF_HIGH}")] >= 2
        assert stats[(batch.DF_DROP_RATIO, "dev")] > 0
    finally:
        result.release()


def test_문서_안_정규화_순위_선별(spark):
    """점수는 0~1, 순위는 문서 안에서 1 부터, 선별은 상위 K **이고** 하한 이상 ([04 §7])."""
    result = run_batch(spark, DEV_DOCS)
    try:
        rows = result.document_candidates.where("url_hash = unhex(%r)" % h("u1").hex()).collect()
        rows.sort(key=lambda r: r["rank"])

        assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
        assert all(0.0 <= r["score"] <= 1.0 for r in rows)
        # 점수 내림차순, 동점은 비교키 사전순 — 결정적이다.
        assert all(
            (a["score"], b["normalized_key"]) >= (b["score"], a["normalized_key"])
            for a, b in zip(rows, rows[1:])
        )
        selected = [r for r in rows if r["selected"]]
        assert 1 <= len(selected) <= THRESHOLDS.per_document_top_k
        assert all(r["rank"] <= 3 and r["score"] >= 0.2 for r in selected)
        assert all(not r["selected"] for r in rows if r["rank"] > 3)
        # 제목에 있는 것이 위쪽이다 — 위치 축.
        assert rows[0]["in_title"]
    finally:
        result.release()


def test_C_value_는_긴_후보를_밀어준다(spark):
    """`workflow` 는 코퍼스에서 늘 더 긴 후보 안에서만 나온다 — 부모가 여럿이라 0 은 아니지만
    (C-value 는 부모 빈도의 **평균**을 뺀다) `agentic workflow` 보다 낮다."""
    result = run_batch(spark, DEV_DOCS)
    try:
        rows = {
            row["normalized_key"]: row
            for row in result.document_candidates.where(
                "url_hash = unhex(%r)" % h("u1").hex()
            ).collect()
        }
        assert rows["workflow"]["c_value"] < rows["agentic workflow"]["c_value"]
        assert rows["agentic workflow"]["c_value"] > 0.0
    finally:
        result.release()


def test_근사_중복은_표시되고_저자와_소스가_실린다(spark):
    docs = [
        doc(
            "f1",
            "보테가 베네타 컬렉션",
            "보테가 베네타가 컬렉션을 공개했다.",
            lang=KO,
            source_id="vogue",
            domain="fashion",
            author="김기자",
        ),
        doc(
            "f2",
            "보테가 베네타 컬렉션 공개",
            "보테가 베네타가 컬렉션을 공개했다.",
            lang=KO,
            source_id="gqkorea",
            domain="fashion",
            author="이기자",
            dup_of="f1",
        ),
    ]
    result = run_batch(
        spark,
        docs,
        domain="fashion",
        options=ExtractionOptions(
            lexicon=LEXICON, tokenize=tk.TokenizeOptions(code_identifiers=False)
        ),
    )
    try:
        rows = result.document_candidates.where("normalized_key = '보테가 베네타'").collect()
        by_doc = {bytes(r["url_hash"]): r for r in rows}
        assert by_doc[h("f1")]["is_dup"] is False and by_doc[h("f2")]["is_dup"] is True
        assert by_doc[h("f1")]["author"] == "김기자" and by_doc[h("f2")]["source_id"] == "gqkorea"
        assert by_doc[h("f1")]["surface"] == "보테가 베네타"
    finally:
        result.release()


def test_해시태그_가중이_점수에_곱해지되_1_을_넘지_않는다(spark):
    docs = [
        doc(
            "t1",
            "가을 룩",
            "#발레코어 가을 코트 #발레코어",
            lang=KO,
            domain="fashion",
            source_id="vogue",
        )
    ]
    plain = run_batch(spark, docs, domain="fashion")
    boosted = run_batch(
        spark, docs, domain="fashion", domain_options=DomainOptions(hashtag_weight=3.0)
    )
    try:

        def score(result):
            (row,) = result.document_candidates.where("normalized_key = '발레코어'").collect()
            return row["score"], row["kind"]

        plain_score, kind = score(plain)
        boosted_score, _ = score(boosted)
        assert kind == tk.HASHTAG
        assert boosted_score >= plain_score and boosted_score <= 1.0
    finally:
        plain.release()
        boosted.release()


def test_약어_전개형_쌍이_대상_문서에서만_나온다(spark):
    docs = DEV_DOCS + [
        doc("u5", "MCP servers", "Model Context Protocol (MCP) servers are everywhere.")
    ]
    result = run_batch(spark, docs, targets=[docs[-1]])
    try:
        (pair,) = result.abbreviations.collect()
        assert (pair["abbreviation_key"], pair["expansion_key"], pair["initials_match"]) == (
            "mcp",
            "model context protocol",
            True,
        )
        assert bytes(pair["url_hash"]) == h("u5")
    finally:
        result.release()


def test_통계에_문서당_평균_후보_수와_신규_유입률이_있다(spark):
    known = spark.createDataFrame([("agentic workflow",), ("postgres",)], "normalized_key string")
    corpus = frame(spark, DEV_DOCS)
    result = batch.extract_batch(
        targets=corpus,
        corpus=corpus,
        domain="dev",
        thresholds=THRESHOLDS,
        options=ExtractionOptions(lexicon=LEXICON),
        domain_options=DomainOptions(),
        extract_run_id=RUN,
        known_keys=known,
    )
    try:
        stats = {(s.metric, s.dimension): s.value for s in result.stats}
        assert stats[(batch.DOCUMENTS, "dev")] == 4
        assert stats[(batch.CANDIDATES_PER_DOC_AVG, "dev")] > 1
        assert 0 < stats[(batch.NEW_CANDIDATE_RATE, "dev")] < 1
        assert stats[(batch.CANDIDATE_NTOKENS, "dev/1")] > 0
        assert stats[(batch.DOCUMENTS_WITHOUT_CANDIDATES, "dev")] == 0
    finally:
        result.release()


# --- 소스 선정 (`extract/source.py`) ------------------------------------------


def test_같은_문서의_옛_실행분은_최근_것_하나만(spark):
    older = doc("u1", "old title", None, run="20260901T000000")
    newer = doc("u1", "new title", None, run="20260902T000000")
    curated = frame(spark, [older, newer])

    rows = source.latest_per_document(curated).collect()
    assert len(rows) == 1 and rows[0]["title"] == "new title"


def test_대상은_실행_목록_또는_발행일_구간(spark):
    a = doc("a", "a", None, run="R1", day="2026-09-01")
    b = doc("b", "b", None, run="R2", day="2026-09-02")
    c = doc("c", "c", None, run="R2", day="2026-09-03", domain="fashion")
    curated = frame(spark, [a, b, c])

    by_run = source.target_documents(curated, source.Selection("dev", ingest_run_ids=("R2",)))
    assert [r["title"] for r in by_run.collect()] == ["b"]

    by_date = source.target_documents(
        curated, source.Selection("dev", date_from=dt.date(2026, 9, 1), date_to=dt.date(2026, 9, 1))
    )
    assert [r["title"] for r in by_date.collect()] == ["a"]

    assert source.ingest_run_ids(curated, domain="dev") == ["R1", "R2"]
    assert source.target_documents(curated, source.Selection("dev")).count() == 0


def test_코퍼스는_대상_최소_발행일에서_N_일_전까지_같은_도메인(spark):
    docs = [
        doc("old", "old", None, day="2026-08-01"),
        doc("edge", "edge", None, day="2026-08-04"),
        doc("t", "t", None, day="2026-09-03"),
        doc("future", "future", None, day="2026-09-10"),
        doc("other", "other", None, day="2026-09-03", domain="fashion"),
    ]
    curated = frame(spark, docs)
    targets = source.target_documents(curated, source.Selection("dev", ingest_run_ids=(RUN,)))
    span = source.date_span(frame(spark, [docs[2]]))

    corpus = source.corpus_documents(curated, domain="dev", span=span, window_days=30)
    assert sorted(r["title"] for r in corpus.collect()) == ["edge", "t"]
    assert targets.count() == 4  # dev 문서 넷 — 도메인 필터만
