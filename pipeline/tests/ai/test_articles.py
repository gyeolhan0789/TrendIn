"""Top5 관련 기사 조회 계약과 AI 입력 구성 테스트."""

import sys
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace

from trendin.ai.articles import (
    RELATED_ARTICLES_SQL,
    TOP_TRENDS_SQL,
    ArticleReference,
    CuratedArticleLoader,
    TrendArticle,
    TrendTarget,
    article_window,
    build_analysis_input,
    select_articles,
)

UTC = timezone.utc


class FakeColumn:
    def __init__(self, name=None):
        self.name = name

    def isin(self, values):
        return "isin", self.name, set(values)

    def isNull(self):
        return "is_null", self.name

    def alias(self, name):
        return self


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows

    def where(self, condition):
        operation, name, *values = condition
        if operation == "isin":
            self.rows = [row for row in self.rows if row[name] in values[0]]
        elif operation == "is_null":
            self.rows = [row for row in self.rows if row[name] is None]
        return self

    def select(self, *columns):
        return self

    def collect(self):
        return self.rows


class FakeReader:
    def __init__(self, rows):
        self.rows = rows
        self.paths = None

    def option(self, name, value):
        return self

    def parquet(self, *paths):
        self.paths = paths
        return FakeFrame(self.rows)


def trend() -> TrendTarget:
    return TrendTarget(
        keyword_id=7,
        keyword="발레코어",
        domain="FASHION",
        period="7D",
        period_start=datetime(2026, 9, 8, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
    )


def article(content_id, *, url=None, body="본문", day=15):
    return TrendArticle(
        content_id=content_id,
        title=f"기사 {content_id}",
        source="vogue",
        url=url or f"https://example.test/{content_id}",
        published_at=datetime(2026, 9, day, tzinfo=UTC),
        body=body,
    )


def reference(content_id, url, object_key):
    return ArticleReference(
        content_id=content_id,
        title=f"기사 {content_id}",
        source="vogue",
        url=url,
        published_at=datetime(2026, 9, 15, tzinfo=UTC),
        body_object_key=object_key,
    )


def test_curated_본문은_object_key와_URL이_모두_일치할_때만_복원한다(monkeypatch):
    functions = SimpleNamespace(
        col=lambda name: FakeColumn(name),
        input_file_name=FakeColumn,
        regexp_replace=lambda column, pattern, replacement: FakeColumn(),
    )
    pyspark = ModuleType("pyspark")
    pyspark_sql = ModuleType("pyspark.sql")
    pyspark_sql.functions = functions
    monkeypatch.setitem(sys.modules, "pyspark", pyspark)
    monkeypatch.setitem(sys.modules, "pyspark.sql", pyspark_sql)

    rows = [
        {
            "_body_object_key": "part-a.parquet",
            "url": "https://same",
            "body": "현재 본문",
            "dup_of": None,
        },
        {
            "_body_object_key": "part-b.parquet",
            "url": "https://same",
            "body": "과거 본문",
            "dup_of": None,
        },
        {
            "_body_object_key": "part-a.parquet",
            "url": "https://unrelated",
            "body": "같은 파일의 다른 기사",
            "dup_of": None,
        },
        {
            "_body_object_key": "part-b.parquet",
            "url": "https://second",
            "body": "두 번째 본문",
            "dup_of": None,
        },
        {
            "_body_object_key": "part-b.parquet",
            "url": "https://duplicate",
            "body": "중복 기사 본문",
            "dup_of": b"representative",
        },
        {
            "_body_object_key": "part-b.parquet",
            "url": "https://empty",
            "body": "   ",
            "dup_of": None,
        },
    ]
    reader = FakeReader(rows)
    loader = object.__new__(CuratedArticleLoader)
    loader._spark = SimpleNamespace(read=reader)
    loader._root = "s3a://curated"

    loaded = loader.load(
        (
            reference(1, "https://same", "part-a.parquet"),
            reference(2, "https://second", "part-b.parquet"),
            reference(3, "https://duplicate", "part-b.parquet"),
            reference(4, "https://empty", "part-b.parquet"),
        )
    )

    assert reader.paths == (
        "s3a://curated/part-a.parquet",
        "s3a://curated/part-b.parquet",
    )
    assert [(item.content_id, item.body) for item in loaded] == [
        (1, "현재 본문"),
        (2, "두 번째 본문"),
    ]


def test_기존_CURRENT_mention_rank_Top5를_재사용한다():
    normalized = " ".join(TOP_TRENDS_SQL.split())
    assert "'CURRENT' = ANY(m.trend_types)" in normalized
    assert "m.mention_rank <= %s" in normalized
    assert "ORDER BY m.mention_rank, k.id" in normalized


def test_관련_기사는_지정한_게시_기간_안에서_최신_20건을_조회한다():
    normalized = " ".join(RELATED_ARTICLES_SQL.split())
    assert "c.published_at >= %s" in normalized
    assert "c.published_at < %s" in normalized
    assert "ORDER BY c.published_at DESC, c.id" in normalized
    assert "LIMIT %s" in normalized


def test_기사_기간은_Top5_기간을_따르고_24H는_최근_7일을_사용한다():
    seven_days = trend()
    assert article_window(seven_days) == (seven_days.period_start, seven_days.period_end)

    thirty_days = TrendTarget(
        keyword_id=7,
        keyword="발레코어",
        domain="FASHION",
        period="30D",
        period_start=datetime(2026, 8, 17, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
    )
    assert article_window(thirty_days) == (thirty_days.period_start, thirty_days.period_end)

    day = TrendTarget(
        keyword_id=7,
        keyword="발레코어",
        domain="FASHION",
        period="24H",
        period_start=datetime(2026, 9, 14, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
    )
    assert article_window(day) == (datetime(2026, 9, 8, tzinfo=UTC), day.period_end)


def test_중복과_빈_본문을_빼고_최신순으로_고른다():
    selected = select_articles(
        (
            article(1, url="https://example.test/same", day=13),
            article(2, url="https://example.test/same", day=15),
            article(3, body="   ", day=14),
            article(4, day=12),
        )
    )
    assert [item.content_id for item in selected] == [2, 4]


def test_기사별_본문과_전체_길이를_제한한다():
    selected = select_articles(
        (article(1, body="가" * 10), article(2, body="나" * 10, day=14)),
        max_articles=2,
        max_body_chars=6,
        max_total_body_chars=9,
    )
    assert [item.body for item in selected] == ["가" * 6, "나" * 3]


def test_AI_입력에_키워드와_기사의_현재_필드를_담는다():
    prompt = build_analysis_input(trend(), (article(1, body="리본 슈즈 출시 내용"),))
    assert "트렌드 키워드: 발레코어" in prompt
    assert "제목: 기사 1" in prompt
    assert "출처: vogue" in prompt
    assert "게시일: 2026-09-15T00:00:00+00:00" in prompt
    assert "URL: https://example.test/1" in prompt
    assert "리본 슈즈 출시 내용" in prompt
