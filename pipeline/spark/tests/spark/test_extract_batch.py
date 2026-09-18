"""후보 추출 배선 ([09 §4] 층 2).

층 1 은 후처리·합치기·필터가 맞는지만 본다. 여기서 보는 것은 **배선** — `mapInPandas` 가
파티션을 모델에 묶어 넣고 세 종류의 행을 내는지, 그것이 문서 × 후보로 펴지는지, 대표 표기와
대표 유형이 배치에서 뽑히는지, 순위와 선별이 [04 §7] 대로 나오는지, 적재 프레임의 칸이
`io/candidates.py` 의 컬럼과 같은지다.

**실제 모델을 부른다.** 파티션 단위 배치 추론이 이 파일이 지키려는 것이라 가짜 인식기로는
아무것도 증명되지 않는다 — 게다가 executor 는 별도 프로세스라 테스트가 캐시에 가짜를 끼워
넣을 수도 없다. `gliner` 가 없으면 통째로 건너뛴다 (`spark/scripts/dev-setup.sh`).

**모델의 판정에 기대지 않는다.** 단정은 배선이 지키는 것만 본다 — 후보가 나온다, 칸이 맞다,
순위가 점수 내림차순이다. "샤넬이 브랜드로 잡힌다" 는 모델의 일이고 `scratchpad/kwlab` 이
정답으로 잰다.

**MinIO · PostgreSQL 은 쓰지 않는다.** 입력은 인메모리 DataFrame(`curated` 의 칸만 흉내),
출력은 프레임을 `collect()` 해서 본다.
"""

from __future__ import annotations

import datetime as dt
import hashlib

import pytest

pytest.importorskip(
    "gliner", reason="실체 인식 모델이 없다 — dev-setup.sh 를 SKIP_MODEL 없이 돌린다"
)

from trendin.spark.extract import batch, source  # noqa: E402
from trendin.spark.extract.document import ExtractionOptions  # noqa: E402
from trendin.spark.extract.entities import RecognizerSpec  # noqa: E402
from trendin.spark.extract.thresholds import ExtractThresholds  # noqa: E402
from trendin.spark.io import candidates as candidates_io  # noqa: E402
from trendin.spark.normalize.lang import KO, MIXED  # noqa: E402

RUN = "20260909T000000"

THRESHOLDS = ExtractThresholds(per_document_top_k=3, score_floor=0.2)
# 문턱을 기본값보다 낮추지 않는다 — 배선 시험이라 후보가 몇 개든 상관없고, 낮추면 문서당
# 후보가 수십 개로 늘어 테스트가 느려진다.
RECOGNIZER = RecognizerSpec(batch_size=4)


def h(text: str) -> bytes:
    return hashlib.sha256(text.encode()).digest()


def doc(
    url: str,
    title: str,
    body: str | None,
    *,
    lang=MIXED,
    source_id="vogue",
    domain="fashion",
    author=None,
    source_country="KR",
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
        "source_country": source_country,
        "published_at": published,
        "published_date": dt.date.fromisoformat(day),
        "dup_of": None if dup_of is None else bytearray(h(dup_of)),
        "ingest_run_id": run,
    }


SCHEMA = (
    "url_hash binary, source_id string, domain string, title string, body string, lang string, "
    "author string, source_country string, published_at timestamp, published_date date, "
    "dup_of binary, ingest_run_id string"
)


def frame(spark, docs):
    return spark.createDataFrame([tuple(d[k] for k in source.COLUMNS) for d in docs], SCHEMA)


def run_batch(spark, docs, *, domain="fashion", options=None, thresholds=None):
    return batch.extract_batch(
        targets=frame(spark, docs),
        domain=domain,
        thresholds=thresholds or THRESHOLDS,
        recognizer=RECOGNIZER,
        options=options or ExtractionOptions(),
        extract_run_id=RUN,
    )


DOCS = [
    doc(
        "u1",
        "샤넬 크루즈 컬렉션이 모나코에서 열렸다",
        "마티유 블라지가 선보인 데님 재킷과 스웨이드 로퍼. 샤넬의 새 시즌이다.",
    ),
    doc(
        "u2",
        "프라다와 미우미우의 가을 신상",
        "프라다가 내놓은 나일론 백과 미우미우의 니트 카디건. 프라다는 이번에도 강했다.",
        author="김기자",
    ),
    doc("u3", "Prada 2027 Resort", None, source_id="wkorea"),  # 본문 없는 문서
]


# --- 배선 ---------------------------------------------------------------------


def test_적재_프레임의_칸이_컬럼_정의와_같다(spark):
    result = run_batch(spark, DOCS)
    try:
        assert tuple(result.document_candidates.columns) == candidates_io.DOCUMENT_CANDIDATE_COLUMNS
        assert tuple(result.abbreviations.columns) == candidates_io.ABBREVIATION_COLUMNS
        assert tuple(result.documents.columns) == candidates_io.EXTRACTED_DOCUMENT_COLUMNS
        assert result.corpus_size == 3 and result.target_count == 3
    finally:
        result.release()


def test_문서마다_후보가_펴지고_본문_없는_문서도_돈다(spark):
    result = run_batch(spark, DOCS)
    try:
        rows = result.document_candidates.collect()
        by_doc: dict[bytes, list] = {}
        for row in rows:
            by_doc.setdefault(bytes(row["url_hash"]), []).append(row)

        # 본문 없는 문서도 제목만으로 돈다 — [03 §2] 가 살려 보낸 이유다.
        assert set(by_doc) == {h("u1"), h("u2"), h("u3")}
        assert all(row["in_title"] for row in by_doc[h("u3")])
        assert all(row["domain"] == "fashion" and row["extract_run_id"] == RUN for row in rows)
        assert all(row["stat_date"] == dt.date(2026, 9, 3) for row in rows)
    finally:
        result.release()


def test_유형이_후보마다_붙는다(spark):
    """모델 라벨이 `kind` 로 간다 (2026-09-16). 옛 경로에서는 토큰 종류였다."""
    result = run_batch(spark, DOCS)
    try:
        kinds = {row["kind"] for row in result.document_candidates.collect()}
        assert kinds and kinds <= set(RECOGNIZER.labels)
    finally:
        result.release()


def test_같은_비교키는_배치_전체에서_한_유형_한_표기다(spark):
    """문서마다 다른 유형이 붙으면 화면의 유형 필터가 문서에 따라 흔들린다 ([04 §4])."""
    result = run_batch(spark, DOCS)
    try:
        seen: dict[str, tuple[str, str]] = {}
        for row in result.document_candidates.collect():
            key = row["normalized_key"]
            assert seen.setdefault(key, (row["surface"], row["kind"])) == (
                row["surface"],
                row["kind"],
            )
        # 서로 다른 문서에 나온 `프라다` 가 한 항목으로 접혔다.
        assert "프라다" in seen
    finally:
        result.release()


def test_DF_는_배치_안에서_센다(spark):
    """⚠️ 뜻이 바뀐 칸이다 — 코퍼스가 아니라 이번 배치의 문서 빈도다 (`extract/batch.py`)."""
    docs = [
        doc("d1", "샤넬 크루즈 컬렉션", "샤넬이 모나코에서 크루즈 컬렉션을 선보였다."),
        doc("d2", "샤넬과 프라다의 가을", "샤넬의 트위드와 프라다의 나일론."),
    ]
    result = run_batch(spark, docs)
    try:
        df = {row["normalized_key"]: row["df"] for row in result.document_candidates.collect()}
        # 두 문서에 걸친 후보는 2, 한 문서에만 있는 것은 1 이다.
        assert df.get("샤넬") == 2
        assert all(1 <= value <= 2 for value in df.values())
    finally:
        result.release()


def test_순위와_선별(spark):
    """문서마다 점수 내림차순 순위, 상위 K 이고 하한 이상이 `selected` ([04 §7])."""
    result = run_batch(spark, DOCS)
    try:
        by_doc: dict[bytes, list] = {}
        for row in result.document_candidates.collect():
            by_doc.setdefault(bytes(row["url_hash"]), []).append(row)

        for rows in by_doc.values():
            rows.sort(key=lambda r: r["rank"])
            assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
            scores = [r["score"] for r in rows]
            assert scores == sorted(scores, reverse=True)
            for row in rows:
                expected = row["rank"] <= 3 and row["score"] >= 0.2
                assert row["selected"] is expected
            assert all(0.0 <= r["score"] <= 1.0 for r in rows)
    finally:
        result.release()


def test_C_value_는_0_이고_BM25_는_기록된다(spark):
    """점수 축이 하나로 줄었다 — 둘 다 칸에만 남는다 (`extract/scoring.py`)."""
    result = run_batch(spark, DOCS)
    try:
        rows = result.document_candidates.collect()
        assert all(row["c_value"] == 0.0 for row in rows)
        assert any(row["bm25"] > 0 for row in rows)
    finally:
        result.release()


def test_근사_중복은_표시되고_저자와_소스가_실린다(spark):
    docs = [*DOCS, doc("u4", "프라다 신상", "프라다의 나일론 백.", dup_of="u2", author="박기자")]
    result = run_batch(spark, docs)
    try:
        rows = result.document_candidates.collect()
        flags = {bytes(row["url_hash"]): row["is_dup"] for row in rows}
        assert flags[h("u4")] is True and flags[h("u1")] is False

        authors = {bytes(row["url_hash"]): row["author"] for row in rows}
        assert authors[h("u2")] == "김기자" and authors[h("u1")] is None
        sources = {bytes(row["url_hash"]): row["source_id"] for row in rows}
        assert sources[h("u3")] == "wkorea"
    finally:
        result.release()


def test_발행_매체의_나라가_후보_행에_실린다(spark):
    """국가 축의 상류가 `curated.source_country` 다 (`extract/source.COLUMNS`).

    이 칸이 끊겨 있던 동안 `keyword_country_daily_metrics` 가 전 키워드를 한 나라로 채웠다.
    """
    docs = [
        doc("k1", "샤넬 크루즈 컬렉션", "샤넬의 새 시즌이다.", source_country="KR"),
        doc("k2", "Prada resort show", "Prada unveiled a nylon bag.", source_country="IT"),
    ]
    result = run_batch(spark, docs)
    try:
        rows = result.document_candidates.collect()
        countries = {bytes(row["url_hash"]): row["source_country"] for row in rows}
        assert countries[h("k1")] == "KR"
        assert countries[h("k2")] == "IT"
    finally:
        result.release()


def test_국가를_모르거나_모양이_틀리면_XX_로_접힌다(spark):
    """기본키에 들어가는 칸이라 `NULL` 을 허용할 수 없다 (`common/countries.py`).

    소문자는 올려 받는다 — 프로필 로더가 막지만 그쪽을 지나지 않는 경로(백필)가 있다.
    """
    docs = [
        doc("n1", "샤넬 크루즈 컬렉션", "샤넬의 새 시즌이다.", source_country=None),
        doc("n2", "프라다 신상", "프라다의 나일론 백.", source_country="kr"),
        doc("n3", "미우미우 니트", "미우미우의 니트 카디건.", source_country="KOR"),
    ]
    result = run_batch(spark, docs)
    try:
        rows = result.document_candidates.collect()
        countries = {bytes(row["url_hash"]): row["source_country"] for row in rows}
        assert countries[h("n1")] == "XX"
        assert countries[h("n2")] == "KR"
        assert countries[h("n3")] == "XX"
    finally:
        result.release()


def test_약어_전개형_쌍이_나온다(spark):
    """모델과 무관한 문자열 규칙이라 추론 경로와 떼어 두었다 (`extract/batch._abbreviations`)."""
    docs = [doc("a", "메시카(Messika)의 하이주얼리", "메시카(Messika)가 새 컬렉션을 냈다.")]
    result = run_batch(spark, docs)
    try:
        (row,) = result.abbreviations.collect()
        assert (row["abbreviation"], row["expansion"]) == ("Messika", "메시카")
        assert row["initials_match"] is False
        assert row["stat_date"] == dt.date(2026, 9, 3) and row["extract_run_id"] == RUN
    finally:
        result.release()


def test_일본어는_브랜드와_인물만_통과한다(spark):
    """언어별 후처리가 executor 까지 간다 (`extract/adapters.py`)."""
    from trendin.spark.normalize.lang import JA

    docs = [
        doc(
            "ja1",
            "ケンゾー「ジャンピング タイガー」",
            "ケンゾー(KENZO)は、虎のビーズ刺繍のスウェットやバックパックを販売。",
            lang=JA,
        )
    ]
    result = run_batch(spark, docs)
    try:
        kinds = {row["kind"] for row in result.document_candidates.collect()}
        assert kinds <= {"브랜드", "인물", "회사 또는 조직"}
    finally:
        result.release()


def test_통계에_문서당_평균과_언어_분포가_있다(spark):
    result = run_batch(spark, DOCS)
    try:
        stats = {(stat.metric, stat.dimension): stat.value for stat in result.stats}
        assert stats[(batch.DOCUMENTS, "fashion")] == 3
        assert stats[(batch.CANDIDATES_PER_DOC_AVG, "fashion")] > 0
        # 다국어 확장의 모니터링 — `unknown` 이 늘면 판별이 새 소스를 못 따라가는 것이다.
        assert stats[(batch.LANGUAGES, f"fashion/{MIXED}")] == 3
        assert any(metric == batch.ENTITY_TYPES for metric, _ in stats)
    finally:
        result.release()


def test_신규_유입률은_이미_아는_키를_뺀다(spark):
    result = run_batch(spark, DOCS)
    known_keys = None
    try:
        keys = [row["normalized_key"] for row in result.document_candidates.collect()]
    finally:
        result.release()

    known_keys = spark.createDataFrame([(key,) for key in keys[:1]], "normalized_key string")
    result = batch.extract_batch(
        targets=frame(spark, DOCS),
        domain="fashion",
        thresholds=THRESHOLDS,
        recognizer=RECOGNIZER,
        options=ExtractionOptions(),
        extract_run_id=RUN,
        known_keys=known_keys,
    )
    try:
        rate = {stat.metric: stat.value for stat in result.stats}[batch.NEW_CANDIDATE_RATE]
        assert 0.0 <= rate < 1.0
    finally:
        result.release()


def test_후보가_없어도_문서_프레임은_나온다(spark):
    """빈 결과는 `documents_without_candidates` 통계로 보여야 한다 ([04 §9])."""
    docs = [doc("empty", "...", "...")]
    result = run_batch(spark, docs)
    try:
        assert result.documents.count() == 1
        stats = {stat.metric: stat.value for stat in result.stats}
        assert stats[batch.DOCUMENTS] == 1
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
    a = doc("a", "a", None, run="R1", day="2026-09-01", domain="dev")
    b = doc("b", "b", None, run="R2", day="2026-09-02", domain="dev")
    c = doc("c", "c", None, run="R2", day="2026-09-03")
    curated = frame(spark, [a, b, c])

    by_run = source.target_documents(curated, source.Selection("dev", ingest_run_ids=("R2",)))
    assert [r["title"] for r in by_run.collect()] == ["b"]

    by_date = source.target_documents(
        curated, source.Selection("dev", date_from=dt.date(2026, 9, 1), date_to=dt.date(2026, 9, 1))
    )
    assert [r["title"] for r in by_date.collect()] == ["a"]

    assert source.ingest_run_ids(curated, domain="dev") == ["R1", "R2"]
    assert source.target_documents(curated, source.Selection("dev")).count() == 0


def test_한국어_문서의_조사가_executor_에서_떨어진다(spark):
    """형태소 분석기가 executor 에서 만들어진다 (`morphology.analyzer_for`)."""
    docs = [doc("ko", "샤넬이 선보인 트위드 재킷", "샤넬의 트위드 재킷이 화제다.", lang=KO)]
    result = run_batch(spark, docs)
    try:
        keys = {row["normalized_key"] for row in result.document_candidates.collect()}
        assert not any(key.endswith(("의", "이", "가", "을", "를")) for key in keys), keys
    finally:
        result.release()
