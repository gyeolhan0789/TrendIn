"""기간별 관련 기사 조회 계약과 AI 입력 구성 테스트."""

import sys
from datetime import datetime, timezone
from decimal import Decimal
from types import ModuleType, SimpleNamespace

from trendin.ai.articles import (
    ARTICLE_CANDIDATE_LIMIT,
    MAX_ARTICLE_BODY_CHARS,
    MAX_ARTICLES,
    MAX_TOTAL_BODY_CHARS,
    RELATED_ARTICLES_SQL,
    TREND_TARGETS_SQL,
    ArticleReference,
    CuratedArticleLoader,
    TrendArticle,
    TrendTarget,
    article_window,
    build_analysis_input,
    input_fingerprint,
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
        trend_types=("NEW", "RISING"),
        mention_count=120,
        previous_mention_count=40,
        growth_amount=80,
        growth_rate=Decimal("200.0"),
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


def test_세_유형을_기간별로_모두_조회하며_Top5_제한이_없다():
    normalized = " ".join(TREND_TARGETS_SQL.split())
    assert "ARRAY['NEW', 'RISING', 'CURRENT']" in normalized
    assert "m.trend_types" in normalized
    assert "m.mention_count" in normalized
    assert "m.growth_rate" in normalized
    assert "mention_rank <=" not in normalized
    assert "LIMIT" not in normalized


def test_관련_기사는_지정한_게시_기간_안에서_최신_20건을_조회한다():
    normalized = " ".join(RELATED_ARTICLES_SQL.split())
    assert "c.published_at >= %s" in normalized
    assert "c.published_at < %s" in normalized
    assert "ORDER BY c.published_at DESC, c.id" in normalized
    assert "LIMIT %s" in normalized
    assert ARTICLE_CANDIDATE_LIMIT == 20


def test_세_기간_모두_최근_30일_기사를_사용한다():
    seven_days = trend()
    assert article_window(seven_days) == (datetime(2026, 8, 16, tzinfo=UTC), seven_days.period_end)

    thirty_days = TrendTarget(
        keyword_id=7,
        keyword="발레코어",
        domain="FASHION",
        period="30D",
        period_start=datetime(2026, 8, 17, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
    )
    assert article_window(thirty_days) == (
        datetime(2026, 8, 16, tzinfo=UTC), thirty_days.period_end
    )

    day = TrendTarget(
        keyword_id=7,
        keyword="발레코어",
        domain="FASHION",
        period="24H",
        period_start=datetime(2026, 9, 14, tzinfo=UTC),
        period_end=datetime(2026, 9, 15, tzinfo=UTC),
        mention_rank=1,
    )
    assert article_window(day) == (datetime(2026, 8, 16, tzinfo=UTC), day.period_end)


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


def test_기본_입력_한도는_최대_8건_기사별_3000자_전체_18000자다():
    assert (MAX_ARTICLES, MAX_ARTICLE_BODY_CHARS, MAX_TOTAL_BODY_CHARS) == (
        8, 3_000, 18_000
    )
    selected = select_articles(tuple(article(i, body="가" * 4_000) for i in range(10)))
    assert len(selected) == 6
    assert all(len(item.body) == 3_000 for item in selected)


def test_AI_입력에_키워드와_기사의_현재_필드를_담는다():
    prompt = build_analysis_input(trend(), (article(1, body="리본 슈즈 출시 내용"),))
    assert "트렌드 키워드: 발레코어" in prompt
    assert "트렌드 유형: NEW, RISING" in prompt
    assert "언급량: 120" in prompt
    assert "직전 기간 언급량: 40" in prompt
    assert "언급 증가량: 80" in prompt
    assert "증가율: 200.0%" in prompt
    assert "제목: 기사 1" in prompt
    assert "출처: vogue" in prompt
    assert "게시일: 2026-09-15T00:00:00+00:00" in prompt
    assert "URL: https://example.test/1" in prompt
    assert "리본 슈즈 출시 내용" in prompt


def test_fingerprint는_유형과_실제_입력_기사에_반응한다():
    from dataclasses import replace

    original = trend()
    articles = (article(1),)
    fingerprint = input_fingerprint(original, articles)

    assert input_fingerprint(replace(original, mention_count=999,
                                     growth_rate=Decimal("999")), articles) == fingerprint
    assert input_fingerprint(
        replace(original, trend_types=("RISING", "NEW")), articles
    ) == fingerprint
    assert input_fingerprint(replace(original, trend_types=("NEW",)), articles) != fingerprint
    assert input_fingerprint(original, (article(1, body="바뀐 본문"),)) != fingerprint
    assert len(fingerprint) == 64


def test_fingerprint는_프롬프트_버전_변경에도_반응한다(monkeypatch):
    original = trend()
    articles = (article(1),)
    fingerprint = input_fingerprint(original, articles)

    monkeypatch.setattr("trendin.ai.articles.PROMPT_VERSION", "trend-analysis-test-version")

    assert input_fingerprint(original, articles) != fingerprint
