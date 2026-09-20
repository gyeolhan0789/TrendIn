"""정제·적재 배선 ([09 §4] 층 2).

층 1 은 정제 규칙이 맞는지만 본다. 여기서 보는 것은 **배선** — UDF 가 표준 문서를 제대로
펴는지, 중복 제거 3단계가 실제로 표시하는지, `curated` 파티션이 [01 §3] 레이아웃으로
쓰이는지, 필터 사유가 처리 이력까지 흐르는지다. 그건 DataFrame 을 실제로 돌려야 드러난다.

**Kafka · MinIO · PostgreSQL 은 쓰지 않는다.** 입력은 인메모리 DataFrame, `curated` 는 임시
디렉터리, `contents` 와 통계는 가짜다.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from trendin.spark.common.config import Config
from trendin.spark.ingest.batch import ENVELOPE_COLUMNS, process_batch
from trendin.spark.ingest.normalize import (
    FILTER_REASON,
    NormalizeStage,
    NormalizeThresholds,
    build_documents,
    resolve_filter_reason,
)
from trendin.spark.ingest.objects import ARTICLE_JSON
from trendin.spark.io import contents as contents_io
from trendin.spark.io import stats as stats_io
from trendin.spark.normalize import curated
from trendin.spark.normalize.dedup import DUP_SAME_DOCUMENT, DUP_SAME_URL, apply_dedup
from trendin.spark.normalize.filters import SHORT_BODY
from trendin.spark.normalize.schema import CURATED_COLUMNS, PARTITION_COLUMNS

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"
OBJECTS = CONTRACT / "objects"
RUN_ID = "20260903T000000"

# 백필이 객체 키와 메타데이터에서 재구성한 봉투 하나 ([02 §6] 3번).
_ENVELOPE = {
    "event_id": "vogue-854414",
    "schema_version": 1,
    "bucket": "raw-data",
    "object_key": "fashion/vogue/rss/2026/09/03/854414/article.json",
    "raw_object_key": None,
    "domain": "fashion",
    "source_id": "vogue",
    "article_id": "854414",
    "run_id": None,
    "url": None,
    "title": None,
    "published_at": None,
    "collected_at": "2026-09-03T02:10:00Z",
    "status": "success",
    "record_count": 1,
    "size_bytes": None,
    "checksum": "sha256-" + "0" * 64,
    "format": "json",
    "compression": "none",
    "failure_reason": None,
    "members_only": None,
    "paywalled": None,
    "source_country": None,
    "_corrupt_record": None,
}

BODY = (
    "보테가 베네타가 2026 가을겨울 컬렉션을 공개했다. "
    "인트레치아토 기법을 재해석한 백과 미니멀한 실루엣의 코트가 중심이다. "
    "브랜드는 이번 시즌 색채를 절제하고 소재의 질감을 앞세웠다고 밝혔다. "
    "이번 쇼는 밀라노에서 열렸고 프론트로에는 여러 배우가 자리했다."
)


@pytest.fixture(scope="module")
def event() -> dict:
    return json.loads((CONTRACT / "article-event.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def article(event) -> dict:
    return json.loads((OBJECTS / event["object_key"]).read_text(encoding="utf-8"))


def config(**overrides) -> Config:
    """테스트용 설정. `load_config` 를 타지 않는 이유는 conf 파일에 의존하지 않으려는 것이다."""
    return Config({"ingest": {"normalize": {}}} | overrides, profile="test")


def articles_frame(spark, event: dict, articles: list[dict]):
    """객체 검증을 통과한 기사 프레임 — 봉투 칸 + `article_json`.

    `ingest/objects.verifier` 가 내주는 형태를 손으로 만든다. MinIO 를 띄우지 않고 정제
    배선만 보려는 것이고, 진짜 검증은 층 1(`test_object_verify.py`)이 검사한다.
    """
    from pyspark.sql.types import StringType, StructField, StructType

    fields = [StructField(name, StringType(), True) for name in ("event_id", ARTICLE_JSON)]
    rows = [
        {
            "event_id": f"{item.get('source')}-{item.get('article_id')}",
            ARTICLE_JSON: json.dumps(item, ensure_ascii=False),
        }
        for item in articles
    ]
    frame = spark.createDataFrame(rows, StructType(fields))
    # 봉투 칸은 `collected_at` 하나만 쓰인다 ([03 §8]).
    from pyspark.sql import functions as F

    return frame.withColumn("collected_at", F.lit(event["collected_at"]))


def tally(documents) -> dict[tuple[str, str], float]:
    """`(지표, 차원) -> 값`. [03 §7] 집계를 읽기 쉽게 펴 둔다."""
    return {
        (stat.metric, stat.dimension): stat.value
        for stat in stats_io.collect_stats(documents)
    }


def documents_of(spark, event: dict, articles: list[dict]):
    return build_documents(
        articles_frame(spark, event, articles),
        ingest_run_id=RUN_ID,
        thresholds=NormalizeThresholds.from_config(config()),
        envelope_columns=("collected_at",),
    )


# --- UDF 배선 -------------------------------------------------------------


def test_표준_문서_칸이_펴진다(spark, article, event):
    """UDF 가 사전을 돌려주고 Spark 가 **이름으로** 칸을 맞춘다. 이름이 어긋난 칸은 오류가
    아니라 `null` 이라, 여기서 실제 값을 확인하는 것이 그 조용한 실패를 막는 자리다."""
    row = documents_of(spark, event, [article | {"body_text": BODY}]).collect()[0]

    assert row["source_id"] == "vogue"
    assert row["domain"] == "fashion"
    assert row["route"] == "rss"
    assert row["url"] == "https://www.vogue.co.kr/2026/09/03/some-article"
    assert row["title"] == "2026 F/W 런웨이가 다시 꺼낸 실루엣"
    assert row["ingest_run_id"] == RUN_ID
    assert row["categories"] == ["fashion", "runway"]
    assert row["published_date"].isoformat() == "2026-09-03"
    assert len(row["url_hash"]) == 32
    # 통과한 문서는 품질 사유가 없다.
    assert row["quality_reason"] is None


def test_부호_없는_지문이_bigint_로_들어간다(spark, article, event):
    """**이 배선이 깨지면 조용히 `null` 이 된다.** 지문의 절반이 `LongType` 상한을 넘는다.

    `null` 이 되면 3단계가 그 문서를 조인에서 빼고, 근사 중복이 아무것도 안 잡힌다.
    """
    row = documents_of(spark, event, [article | {"body_text": BODY}]).collect()[0]

    assert row["simhash"] is not None
    assert -(1 << 63) <= row["simhash"] <= (1 << 63) - 1


def test_짧은_본문은_품질_사유가_붙는다(spark, article, event):
    row = documents_of(spark, event, [article | {"body_text": "짧다"}]).collect()[0]

    assert row["quality_reason"] == SHORT_BODY


# --- 중복 제거 3단계 ([03 §6]) --------------------------------------------


def test_1단계_같은_문서는_나중_것을_버린다(spark, article, event):
    """같은 `(source_id, source_document_id)`. 생산자 불변식 7 이 거의 다 막지만
    `--force` 재처리에는 이 단계가 마지막 방어선이다."""
    same = article | {"body_text": BODY}
    # URL 이 달라도 같은 기사다 — 소스가 정규 URL 을 바꾼 경우.
    other_url = same | {"url": "https://www.vogue.co.kr/2026/09/03/some-article?p=854414"}

    rows = apply_dedup(documents_of(spark, event, [same, other_url])).collect()
    reasons = sorted(row["dup_reason"] or "" for row in rows)

    assert reasons == ["", DUP_SAME_DOCUMENT]


def test_2단계_같은_URL_은_대표_하나만_남는다(spark, article, event):
    """`article_id` 가 달라도 정규화된 URL 이 같으면 같은 문서다."""
    first = article | {"body_text": BODY}
    second = first | {"article_id": "999999", "url": first["url"] + "?utm_source=x"}

    rows = apply_dedup(documents_of(spark, event, [first, second])).collect()
    reasons = sorted(row["dup_reason"] or "" for row in rows)

    assert reasons == ["", DUP_SAME_URL]


def test_3단계_근사_중복은_지우지_않고_표시한다(spark, article, event):
    """**표적은 두산 계열의 같은 보도자료 동시 게재다** — `article_id` 도 URL 도 달라서
    지문 말고는 잡히지 않는다.

    지우지 않는 이유는 판별이 임계값에 민감해서다. 지워버리면 임계값을 조정했을 때 되살릴
    방법이 객체 재처리뿐이다 ([03 §6]).

    **본문을 그대로 둔 쌍을 쓴다.** 가벼운 편집이 섞인 쌍은 문서 길이에 따라 거리가 8~13 을
    오가서(`test_simhash.py` 의 측정) 문턱 경계에 걸린다. 여기서 보려는 것은 배선이 도는지지
    문턱이 맞는지가 아니고, 그 문턱은 [S6] 이 실데이터로 정한다 ([09 §7] 항목 5).
    """
    original = article | {"body_text": BODY}
    reposted = {
        **original,
        "source": "gqkorea",
        "article_id": "700001",
        "url": "https://www.gqkorea.co.kr/2026/09/03/other-article",
    }

    rows = apply_dedup(documents_of(spark, event, [original, reposted])).collect()
    marked = [row for row in rows if row["dup_of"] is not None]

    # 두 행 모두 남는다 — 버리지 않는다.
    assert len(rows) == 2
    # 하나만 대표를 가리킨다. 대표 자신은 `null` 이다.
    assert len(marked) == 1
    # 1·2 단계에는 걸리지 않았다 — 그래서 3단계가 필요하다.
    assert all(row["dup_reason"] is None for row in rows)


def test_본문_없는_문서는_서로_중복이_되지_않는다(spark, article, event):
    """**dev 도메인 전량이 이 경로다.** 제목만으로 SimHash 를 계산하면 해밍 거리가 우연히
    가까워져 도메인 하나가 통째로 중복으로 판별될 수 있다 ([03 §6]).

    `simhash()` 가 본문 없는 문서에 `None` 을 내므로 조인에 걸리지 않는다.
    """
    def hn(article_id: str, title: str) -> dict:
        return {
            "schema_version": 1,
            "domain": "dev",
            "source": "hn",
            "route": "api",
            "article_id": article_id,
            "url": f"https://news.ycombinator.com/item?id={article_id}",
            "title": title,
            "published_at": "2026-09-03T10:00:00+09:00",
            "collected_at": "2026-09-03T02:10:00Z",
        }

    rows = apply_dedup(
        documents_of(spark, event, [hn("1", "Kubernetes 1.32 released"), hn("2", "Rust 1.90 out")])
    ).collect()

    assert all(row["simhash"] is None for row in rows)
    assert all(row["dup_of"] is None for row in rows)


def test_사유는_중복이_품질보다_앞선다(spark, article, event):
    """같은 문서가 중복이면서 짧을 때 중복으로 센다 — 중복은 상류(수집·재처리)의 신호이고
    품질은 소스의 신호라, 진단에는 앞쪽이 쓸모 있다."""
    short = article | {"body_text": "짧다"}
    # `article_id` 를 바꿔야 2단계(같은 URL)를 탄다. 그대로 두면 1단계(같은 문서)가 먼저
    # 잡고, 그건 이 테스트가 보려는 것이 아니다.
    duplicate = short | {"article_id": "999999", "url": short["url"] + "?utm_source=x"}

    rows = resolve_filter_reason(apply_dedup(documents_of(spark, event, [short, duplicate])))
    reasons = sorted(row[FILTER_REASON] for row in rows.collect())

    # 대표는 품질로 걸리고, 중복인 쪽은 중복으로 걸린다.
    assert reasons == [DUP_SAME_URL, SHORT_BODY]


# --- `curated` Parquet ([01 §3]) -----------------------------------------


def test_파티션_레이아웃대로_쓰인다(writable_spark, article, event, tmp_path):
    """`domain/published_date/source/ingest_run_id` 4단이다.

    4단을 유지하는 이유는 재처리 단위다 — `--force` 로 다시 돌릴 때 "그 실행이 쓴 것" 을
    통째로 지우고 다시 쓸 수 있어야 한다 ([02 §6]).
    """
    root = str(tmp_path / "curated")
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )

    curated.write(documents, config(), root=root)

    written = writable_spark.read.parquet(root)
    assert set(PARTITION_COLUMNS) <= set(written.columns)
    # 파티션 컬럼은 경로에만 있고 파일 안에 저장되지 않는다 — Spark 가 읽을 때 되살린다.
    assert (tmp_path / "curated" / "domain=fashion" / "published_date=2026-09-03").exists()
    assert (
        tmp_path
        / "curated"
        / "domain=fashion"
        / "published_date=2026-09-03"
        / "source=vogue"
        / f"ingest_run_id={RUN_ID}"
    ).exists()


def test_curated_에_내부_판정값이_섞이지_않는다(writable_spark, article, event, tmp_path):
    """`basis`·`simhash`·`quality_reason` 은 `extract` 의 입력에 있을 값이 아니다.

    섞이면 나중에 "이 칸은 무엇인가" 를 되짚어야 한다.
    """
    root = str(tmp_path / "curated")
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )

    curated.write(documents, config(), root=root)

    columns = set(writable_spark.read.parquet(root).columns)
    assert set(CURATED_COLUMNS) - {"source_id"} <= columns
    assert not columns & {"basis", "simhash", "quality_reason", FILTER_REASON, "dup_reason"}


def test_body_object_key_는_파티션_디렉터리가_아니라_파일을_가리킨다(
    writable_spark, article, event, tmp_path
):
    """[01 §3] 이 "그 문서가 들어 있는 Parquet **파일**의 객체 키" 로 정했다.

    쓰기 전에는 part 파일 이름을 알 수 없으므로 쓴 뒤에 되읽어 `input_file_name()` 으로 얻는다.
    """
    root = str(tmp_path / "curated")
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )
    curated.write(documents, config(), root=root)

    keys = curated.body_object_keys(writable_spark, config(), documents, root=root).collect()

    assert len(keys) == 1
    key = keys[0]["body_object_key"]
    assert key.endswith(".parquet")
    # 버킷 이름은 설정이 들고 있다 — 키에 섞으면 버킷을 옮길 때 옛 행이 못 따라온다.
    assert not key.startswith(root)
    assert key.startswith("domain=fashion/")


def test_같은_실행을_다시_써도_행_수가_늘지_않는다(writable_spark, article, event, tmp_path):
    """`overwrite` + `partitionOverwriteMode=dynamic` 이 `--force` 재처리를 성립시킨다.

    `append` 로 두면 같은 문서가 파티션에 하나 더 쌓여 `extract` 입력이 중복된다.
    """
    root = str(tmp_path / "curated")
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )

    curated.write(documents, config(), root=root)
    curated.write(documents, config(), root=root)

    assert writable_spark.read.parquet(root).count() == 1


# --- 통계 ([03 §7]) ------------------------------------------------------


def test_통계는_버리기_전에_센다(spark, article, event):
    """분모가 입력 건수다. 버린 뒤에 세면 생존율을 계산할 수 없다."""
    kept = article | {"body_text": BODY}
    dropped = article | {"article_id": "999999", "url": "https://a.com/x", "body_text": "짧다"}

    documents = resolve_filter_reason(apply_dedup(documents_of(spark, event, [kept, dropped])))
    collected = tally(documents)

    assert collected[(stats_io.INPUT, "")] == 2
    assert collected[(stats_io.KEPT, "")] == 1
    assert collected[(stats_io.SURVIVAL_RATE, "")] == 0.5
    assert collected[(stats_io.EXCLUDED, SHORT_BODY)] == 1


def test_본문_없는_문서를_종류별로_센다(spark, article, event):
    """[03 §7] 이 "이 목록에서 가장 값진 지표" 로 꼽은 것이다.

    회원 전용 판별은 CSS 선택자 하나에 달려 있고 매체가 템플릿을 바꾸면 조용히 깨진다.
    깨지는 방향이 둘인데 둘 다 나쁘고, 하나는 법적 문제다(불변식 2). `members_only` 와
    `route=api` 를 합치면 어느 쪽이 깨졌는지 알 수 없다.
    """
    members_only = {k: v for k, v in article.items() if k != "body_text"} | {"members_only": True}

    documents = resolve_filter_reason(apply_dedup(documents_of(spark, event, [members_only])))
    collected = tally(documents)

    assert collected[(stats_io.BODY_MISSING, stats_io.BODY_MISSING_MEMBERS_ONLY)] == 1


def test_유료_표시는_회원_전용과_다른_이유로_센다(spark, article, event):
    bodyless = {k: v for k, v in article.items() if k != "body_text"}
    members_only = bodyless | {"members_only": True}
    paywalled = bodyless | {"article_id": "854415", "url": "https://a.com/p", "paywalled": True}

    documents = resolve_filter_reason(
        apply_dedup(documents_of(spark, event, [members_only, paywalled]))
    )
    collected = tally(documents)

    assert collected[(stats_io.BODY_MISSING, stats_io.BODY_MISSING_MEMBERS_ONLY)] == 1
    assert collected[(stats_io.BODY_MISSING, stats_io.BODY_MISSING_PAYWALLED)] == 1


def test_미래_시각_보정_건수를_센다(spark, article, event):
    """소스 이상 신호다 ([03 §7]).

    "값이 없어서 대체한" 건수는 세지 않는다 — 그 대체가 일어나지 않는다 ([03 §3]).
    0 이 나올 것이 확실한 지표를 세면 대시보드만 길어진다.
    """
    future = article | {"body_text": BODY, "published_at": "2027-01-01T00:00:00+09:00"}

    documents = resolve_filter_reason(apply_dedup(documents_of(spark, event, [future])))
    collected = tally(documents)

    assert collected[(stats_io.PUBLISHED_AT_CORRECTED, "")] == 1


# --- `contents` 행 ([03 §8]) ---------------------------------------------


def test_contents_행에_본문과_요약이_없다(writable_spark, article, event, tmp_path):
    """**v2 에서 `summary` 컬럼이 사라진 것이 방어다.** 소스가 준 리드문은 매체의 저작물이라
    화면에 나가면 불변식 3 을 깬다.

    v1 에서는 빈 컬럼이 있어 "여기에 넣지 마라" 를 규칙으로 지켜야 했는데, 이제 스키마가
    대신 막는다 — 그리고 이 테스트가 그 스키마를 다시 확인한다.
    """
    root = str(tmp_path / "curated")
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )
    curated.write(documents, config(), root=root)
    keys = curated.body_object_keys(writable_spark, config(), documents, root=root)

    rows = contents_io.contents_rows(documents.join(keys, on="url_hash", how="left"))

    assert set(rows.columns) == set(contents_io.STAGE_COLUMNS)
    assert "body" not in rows.columns
    assert "summary" not in rows.columns
    row = rows.collect()[0]
    assert row["source"] == "vogue"
    assert row["body_object_key"].endswith(".parquet")


# --- 배치 배선 -----------------------------------------------------------


class FakeConnection:
    """`Ledger.transaction()` 이 내주는 연결 대신. 누가 같은 연결을 받았는지만 본다."""

    def __init__(self):
        self.committed = False
        self.rolled_back = False


class FakeLedger:
    def __init__(self, *, fail_record: bool = False):
        self.recorded = []
        self.connections: list[FakeConnection] = []
        self.fail_record = fail_record

    def filter_new(self, events):
        return events

    def record(self, rows, *, conn=None):
        if self.fail_record:
            raise RuntimeError("처리 이력 쓰기가 죽었다 (테스트)")
        self.recorded.extend(row.asDict() for row in rows.collect())
        self.connections.append(conn)

    def transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def _tx():
            conn = FakeConnection()
            try:
                yield conn
                conn.committed = True
            except BaseException:
                conn.rolled_back = True
                raise

        return _tx()


class FakeDlq:
    def __init__(self):
        self.written = []

    def ensure_schema(self):
        pass

    def write(self, rejected):
        self.written.extend(row.asDict() for row in rejected.collect())


class FakeContents:
    def __init__(self, *, fail: bool = False):
        self.upserted = []
        self.connections = []
        self.fail = fail

    def upsert(self, rows, *, conn=None):
        if self.fail:
            # 2026-09-18 의 `StringDataRightTruncation` 자리다.
            raise RuntimeError("contents upsert 가 죽었다 (테스트)")
        self.upserted.extend(row.asDict() for row in rows.collect())
        self.connections.append(conn)


def kafka_rows(spark, events):
    """봉투 사전 목록을 배치가 받는 프레임으로. 발판은 `envelope_support` 가 든다."""
    from envelope_support import frame_from_events

    return frame_from_events(spark, events)


def fake_verifier(article_json: str):
    """객체 검증을 통과시키고 내용을 실어 준다 — 진짜 구현이 하는 일과 같은 형태다."""

    def _verify(articles):
        from pyspark.sql import functions as F

        return (
            articles.withColumn("error_type", F.lit(None).cast("string"))
            .withColumn("detail", F.lit(""))
            .withColumn(ARTICLE_JSON, F.lit(article_json))
        )

    return _verify


def test_필터_사유가_처리_이력의_detail_까지_흐른다(spark, article, event, tmp_path):
    """**처리 이력 한 행만 봐도 그 문서가 왜 `curated` 에 없는지 알 수 있어야 한다.**

    `ledger_status` 는 건드리지 않는다 — 필터로 버린 것은 실패가 아니라 판정이다 ([03 §6]).
    그래서 DLQ 로도 가지 않는다: 짧은 본문과 근사 중복은 생산자가 고칠 것이 없다.
    """
    ledger, dlq, contents, stats = FakeLedger(), FakeDlq(), FakeContents(), stats_io.RunStats()
    stage = NormalizeStage(
        config(),
        ingest_run_id=RUN_ID,
        envelope_columns=ENVELOPE_COLUMNS,
        contents=contents,
        stats=stats,
    )

    result = process_batch(
        kafka_rows(spark, [event]),
        job="ingest",
        ledger=ledger,
        dlq=dlq,
        verify_objects=fake_verifier(json.dumps(article | {"body_text": "짧다"})),
        normalize=stage,
    )

    assert (result.articles, result.filtered, result.rejected) == (1, 1, 0)
    # 필터로 버린 것은 DLQ 로 가지 않는다.
    assert dlq.written == []
    row = ledger.recorded[0]
    assert (row["status"], row["stage"], row["detail"]) == ("COMPLETED", "normalize", SHORT_BODY)
    # 버려진 문서는 `contents` 에도 들어가지 않는다.
    assert contents.upserted == []


def test_요약_이벤트는_정제를_타지_않는다(spark, event):
    """읽을 객체가 없다. `article_json` 이 `null` 이라 정제가 빈 프레임을 받는다 —
    **검증하지 않은 내용을 정제하지 않는다.**"""
    summary = json.loads((CONTRACT / "run-summary-success.json").read_text(encoding="utf-8"))
    ledger, dlq, stats = FakeLedger(), FakeDlq(), stats_io.RunStats()
    stage = NormalizeStage(
        config(),
        ingest_run_id=RUN_ID,
        envelope_columns=ENVELOPE_COLUMNS,
        contents=None,
        stats=stats,
    )

    result = process_batch(
        kafka_rows(spark, [summary]),
        job="ingest",
        ledger=ledger,
        dlq=dlq,
        verify_objects=fake_verifier("{}"),
        normalize=stage,
    )

    assert (result.summaries, result.filtered) == (1, 0)
    assert ledger.recorded[0]["stage"] == "contract"


# --- 백필 프레임 ([02 §6] 모드 B) ----------------------------------------


def test_재구성한_프레임이_카프카_경로와_같은_칸을_갖는다(spark, event):
    """**이것이 모드 B 의 유일한 위험이다.** [02 §6] 4번이 "이후는 모드 A 와 같은 코드 경로"
    라고 정했으므로, 재구성한 프레임의 칸이 평시 경로의 결과와 어긋나면
    `process_batch` 가 그 자리에서 죽는다.

    칸 이름은 [02 §6] 문구에 없어서 코드로만 지켜지는 계약이다 — 그래서 테스트로 고정한다.
    """
    from trendin.spark.ingest import backfill

    kafka_columns = set(kafka_rows(spark, [event]).columns)
    reconstructed = backfill.events_frame(spark, [_ENVELOPE])

    # 재구성 쪽에는 판별 칸이 이미 붙어 있다 (`decided=True` 로 넣기 때문이다).
    decided = {"event_shape", "error_type", "detail", "ledger_status", "stage"}
    assert set(reconstructed.columns) == kafka_columns | decided


def test_재구성한_이벤트는_기사로_판별돼_정제까지_간다(spark):
    """`with_decision` 을 태우지 않으므로 판별 칸을 직접 채운다.

    태웠다면 **재구성한 모든 이벤트가 `CONTRACT_VIOLATION` 으로 DLQ 에 간다** — 봉투에
    `url`·`published_at` 이 없기 때문이다. 검증하는 대상이 우리가 방금 만든 봉투이므로
    그 검증에 뜻이 없다 (`ingest/backfill.py` 의 표).
    """
    from trendin.spark.ingest import backfill

    row = backfill.events_frame(spark, [_ENVELOPE]).collect()[0]

    assert row["event_shape"] == "ARTICLE"
    assert row["error_type"] is None
    assert (row["ledger_status"], row["stage"]) == ("COMPLETED", "normalize")
    # 객체 키에서 만든 값들.
    assert row["event_id"] == "vogue-854414"
    assert row["object_key"].endswith("/article.json")
    # Kafka 에서 온 것이 아니라는 표시. 0 을 넣으면 진짜 0번 파티션의 이벤트와 섞인다.
    assert row["partition"] is None
    assert row["offset"] == -1
    # 원본 메시지가 없으므로 DLQ 가 보여 줄 것으로 객체 키를 넣는다.
    assert row["raw_value"].startswith("s3://")


def test_빈_목록도_프레임이_된다(spark):
    """범위 안에 객체가 없는 것은 정상이다 — 그 날 발행된 기사가 없으면 그렇다."""
    from trendin.spark.ingest import backfill

    assert backfill.events_frame(spark, []).count() == 0


# --- 평시 경로 프레임 (S15P21A102-247 코드리뷰) -----------------------------


def test_평시_경로_프레임에는_판별_칸이_없다(spark, event):
    """**판별 칸이 붙어 있으면 `classify` 가 통째로 건너뛰어진다.**

    그러면 도메인 허용 목록 검사도 같이 빠지고, 목록 밖 값이 장부에 들어왔을 때 정제
    단계의 `keywords_domain` 이 `ValueError` 를 올려 배치가 통째로 죽는다. 그 행 하나만
    DLQ 로 가야 한다.

    칸이 그 밖에는 Kafka 시절과 같아야 한다는 것도 같이 고정한다 — 어긋나면
    `process_batch` 가 그 자리에서 죽는다.
    """
    from trendin.spark.ingest import backfill

    frame = backfill.envelope_frame(spark, [_ENVELOPE])

    assert set(frame.columns) == set(kafka_rows(spark, [event]).columns)
    assert not {"event_shape", "error_type", "ledger_status", "stage"} & set(frame.columns)


# --- 다중 마이크로배치 (리뷰 P1 — curated 유실 · 통계 덮어쓰기) --------------


def test_실행_안_두_번째_쓰기는_append_라_앞_배치가_남는다(
    writable_spark, article, event, tmp_path
):
    """`AvailableNow` 가 배치를 둘 내면 둘은 같은 `ingest_run_id` 파티션에 쓴다.

    둘 다 `overwrite` 면 배치 2 가 파티션을 통째로 갈아치워 배치 1 의 문서가 사라진다.
    """
    root = str(tmp_path / "curated")
    first = article | {"body_text": BODY}
    second = article | {
        "article_id": "999999",
        "url": "https://www.vogue.co.kr/b",
        "body_text": BODY,
    }

    curated.write(
        resolve_filter_reason(apply_dedup(documents_of(writable_spark, event, [first]))),
        config(),
        root=root,
        mode="overwrite",
    )
    curated.write(
        resolve_filter_reason(apply_dedup(documents_of(writable_spark, event, [second]))),
        config(),
        root=root,
        mode="append",
    )

    assert writable_spark.read.parquet(root).count() == 2


def test_정제_단계는_첫_배치만_overwrite_하고_그_뒤는_append_한다(
    writable_spark, article, event, tmp_path, monkeypatch
):
    modes = []
    real_write = curated.write

    def spy(documents, cfg, *, root=None, mode="overwrite"):
        modes.append(mode)
        return real_write(documents, cfg, root=str(tmp_path / "curated"), mode=mode)

    monkeypatch.setattr(curated, "write", spy)
    monkeypatch.setattr(curated, "body_object_keys", lambda *a, **k: None)
    stage = NormalizeStage(
        config(), ingest_run_id=RUN_ID, envelope_columns=ENVELOPE_COLUMNS, contents=None, stats=None
    )
    verify = fake_verifier(json.dumps(article | {"body_text": BODY}))
    verified = verify(kafka_rows(writable_spark, [event]))

    stage(verified)
    stage(verified)

    assert modes == ["overwrite", "append"]


def test_통계는_배치를_누적하고_비율은_끝에_다시_계산한다(spark, article, event):
    """배치마다 upsert 하면 뒤 배치가 앞 배치를 덮는다. 누적기는 건수를 더하고 비율을 끝에 낸다."""
    kept = article | {"body_text": BODY}
    dropped = article | {"article_id": "999999", "url": "https://a.com/x", "body_text": "짧다"}
    run = stats_io.RunStats()

    run.add_batch(resolve_filter_reason(apply_dedup(documents_of(spark, event, [kept]))))
    run.add_batch(resolve_filter_reason(apply_dedup(documents_of(spark, event, [kept, dropped]))))
    collected = {(s.metric, s.dimension): s.value for s in run.finalize()}

    assert collected[(stats_io.INPUT, "")] == 3
    assert collected[(stats_io.KEPT, "")] == 2
    assert collected[(stats_io.EXCLUDED, SHORT_BODY)] == 1
    assert collected[(stats_io.SURVIVAL_RATE, "")] == pytest.approx(2 / 3)
    assert collected[(stats_io.BODY_LEN_MAX, "rss")] > 0


# --- 객체 검증은 배치당 한 번만 돈다 (리뷰 P1 — lineage 재계산) -----------------


def test_객체_검증_UDF_는_문서당_한_번만_돈다(spark, article, event):
    """정제 결과를 lazy 조인으로 돌려주면 처리 이력을 쓸 때 검증·정제 UDF 가 다시 돈다.

    그러면 `curated` 에 쓴 문서와 처리 이력의 판정이 서로 다른 계산에서 나온다. Spark
    accumulator 로 UDF 호출 수를 세어 정확히 문서 수만큼인지 본다.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import StringType

    calls = spark.sparkContext.accumulator(0)
    payload = json.dumps(article | {"body_text": BODY})

    def _fetch(_event_id):
        calls.add(1)
        return payload

    fetch_udf = F.udf(_fetch, StringType())

    def counting_verifier(articles):
        return (
            articles.withColumn("error_type", F.lit(None).cast("string"))
            .withColumn("detail", F.lit(""))
            .withColumn(ARTICLE_JSON, fetch_udf(F.col("event_id")))
        )

    ledger, dlq = FakeLedger(), FakeDlq()
    stage = NormalizeStage(
        config(), ingest_run_id=RUN_ID, envelope_columns=ENVELOPE_COLUMNS, contents=None, stats=None
    )
    # curated 쓰기는 이 테스트의 관심이 아니다 — 파일을 못 쓰는 호스트에서도 돌게 막는다.
    stage._persist = lambda documents: stage.last_result  # noqa: SLF001

    result = process_batch(
        kafka_rows(spark, [event]),
        job="ingest",
        ledger=ledger,
        dlq=dlq,
        verify_objects=counting_verifier,
        normalize=stage,
    )

    assert result.articles == 1
    assert len(ledger.recorded) == 1
    assert calls.value == 1


# --- 적재는 한 트랜잭션이고, 죽으면 본문을 되돌린다 (S15P21A102-341) ----------------


def _stage_with_fs_root(tmp_path, *, contents, stats=None):
    """임시 디렉터리를 `curated` 로 쓰는 정제 단계. MinIO 없이 쓰기·되돌리기를 본다."""
    return NormalizeStage(
        config(),
        ingest_run_id=RUN_ID,
        envelope_columns=ENVELOPE_COLUMNS,
        contents=contents,
        stats=stats,
        root=str(tmp_path / "curated"),
    )


def _run_partitions(tmp_path) -> list[pathlib.Path]:
    return sorted((tmp_path / "curated").rglob(f"ingest_run_id={RUN_ID}"))


def test_contents_upsert_가_죽으면_curated_파티션과_이력이_남지_않는다(
    writable_spark, article, event, tmp_path
):
    """2026-09-18 의 재현이다. `contents` upsert 에서 죽은 회차가 본문만 남기고 이력을 못 적어,
    다음 회차가 같은 문서를 다시 써서 코퍼스 전체가 39벌 쌓였다.

    이제는 그 회차가 쓴 파티션을 지우고 이력도 없다 — 다음 회차가 같은 문서를 다시 쓰지만
    **한 벌**만 남는다.
    """
    ledger, dlq = FakeLedger(), FakeDlq()
    stage = _stage_with_fs_root(tmp_path, contents=FakeContents(fail=True))

    with pytest.raises(RuntimeError, match="contents upsert"):
        process_batch(
            kafka_rows(writable_spark, [event]),
            job="ingest",
            ledger=ledger,
            dlq=dlq,
            verify_objects=fake_verifier(json.dumps(article | {"body_text": BODY})),
            normalize=stage,
            run_id=RUN_ID,
        )

    assert _run_partitions(tmp_path) == []
    assert ledger.recorded == []
    assert stage.uncommitted_partitions == frozenset()


def test_처리_이력_쓰기가_죽어도_curated_파티션이_남지_않는다(
    writable_spark, article, event, tmp_path
):
    """`contents` 는 됐는데 이력에서 죽는 경우. 같은 트랜잭션이라 `contents` 도 롤백되고,
    본문은 보상 삭제로 사라진다. 어느 쪽에서 죽든 결과는 같아야 한다."""
    ledger, dlq, contents = FakeLedger(fail_record=True), FakeDlq(), FakeContents()
    stage = _stage_with_fs_root(tmp_path, contents=contents)

    with pytest.raises(RuntimeError, match="처리 이력"):
        process_batch(
            kafka_rows(writable_spark, [event]),
            job="ingest",
            ledger=ledger,
            dlq=dlq,
            verify_objects=fake_verifier(json.dumps(article | {"body_text": BODY})),
            normalize=stage,
            run_id=RUN_ID,
        )

    assert _run_partitions(tmp_path) == []
    # 가짜 연결이 롤백을 받았다 — 진짜에서는 `jdbc.connection` 이 같은 일을 한다.
    assert contents.connections and contents.connections[0].rolled_back


def test_정상_회차는_contents_와_이력을_같은_연결로_쓰고_파티션을_남긴다(
    writable_spark, article, event, tmp_path
):
    ledger, dlq, contents = FakeLedger(), FakeDlq(), FakeContents()
    stage = _stage_with_fs_root(tmp_path, contents=contents)

    result = process_batch(
        kafka_rows(writable_spark, [event]),
        job="ingest",
        ledger=ledger,
        dlq=dlq,
        verify_objects=fake_verifier(json.dumps(article | {"body_text": BODY})),
        normalize=stage,
        run_id=RUN_ID,
    )

    assert result.articles == 1
    assert len(_run_partitions(tmp_path)) == 1
    assert len(contents.upserted) == 1
    assert contents.upserted[0]["body_object_key"].endswith(".parquet")
    # 한 연결이다. 그 연결이 커밋됐고, 되돌릴 파티션은 남아 있지 않다.
    assert contents.connections == ledger.connections
    assert ledger.connections[0].committed
    assert stage.uncommitted_partitions == frozenset()
    # 이력의 run_id 는 봉투의 값(NULL)이 아니라 이 실행의 번호다.
    assert ledger.recorded[0]["run_id"] == RUN_ID


def test_contents_행은_커밋_전까지_쓰이지_않는다(writable_spark, article, event, tmp_path):
    """정제 단계는 행을 들고만 있다. 이력 없이 `contents` 만 들어가는 경로가 없어야 한다."""
    contents = FakeContents()
    stage = _stage_with_fs_root(tmp_path, contents=contents)
    verified = fake_verifier(json.dumps(article | {"body_text": BODY}))(
        kafka_rows(writable_spark, [event])
    )

    stage(verified)

    assert contents.upserted == []
    assert len(stage.uncommitted_partitions) == 1
    stage.flush(None)
    assert len(contents.upserted) == 1
    # 쓴 것만으로는 안 끝난다 — 커밋이 확인돼야 되돌릴 대상에서 빠진다.
    assert len(stage.uncommitted_partitions) == 1
    stage.mark_committed()
    assert stage.uncommitted_partitions == frozenset()


def test_되돌리기는_이_실행의_파티션만_지운다(writable_spark, article, event, tmp_path):
    """파티션의 마지막 단이 `ingest_run_id` 라 다른 실행이 같은 날짜·소스에 쓴 것은 남는다."""
    from pyspark.sql import functions as F

    other = "20260901T000000"
    root = str(tmp_path / "curated")
    stage = _stage_with_fs_root(tmp_path, contents=None)
    verified = fake_verifier(json.dumps(article | {"body_text": BODY}))(
        kafka_rows(writable_spark, [event])
    )
    stage(verified)
    assert len(_run_partitions(tmp_path)) == 1
    # 다른 실행이 같은 날짜·소스 파티션 아래에 쓴 것. 테스트 세션에는 `partitionOverwriteMode=
    # dynamic` 이 없어 `overwrite` 가 루트를 통째로 비우므로 정제 단계 **뒤에** append 로 쓴다.
    documents = resolve_filter_reason(
        apply_dedup(documents_of(writable_spark, event, [article | {"body_text": BODY}]))
    )
    curated.write(
        documents.withColumn("ingest_run_id", F.lit(other)), config(), root=root, mode="append"
    )

    removed = stage.rollback()

    assert removed >= 1
    assert _run_partitions(tmp_path) == []
    assert sorted((tmp_path / "curated").rglob(f"ingest_run_id={other}")) != []
