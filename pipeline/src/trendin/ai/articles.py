"""기간별 트렌드의 관련 기사를 조회하고 AI 입력으로 구성한다."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from trendin.ai.analyzer import PROMPT_VERSION

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

    from trendin.spark.common.config import Config

ARTICLE_CANDIDATE_LIMIT = 20
MAX_ARTICLES = 8
MAX_ARTICLE_BODY_CHARS = 3_000
MAX_TOTAL_BODY_CHARS = 18_000
URI_SCHEME_RE = r"^[a-zA-Z0-9+.-]+://"


TREND_TARGETS_SQL = """
SELECT k.id, k.name, k.domain, m.period::text, m.period_start, m.period_end,
       m.mention_rank, m.trend_types, m.mention_count, m.previous_mention_count,
       m.growth_amount, m.growth_rate
  FROM keyword_metrics m
  JOIN keywords k ON k.id = m.keyword_id
 WHERE k.domain = %s
   AND m.period = %s::metric_period
   AND m.period_start = %s
   AND m.period_end = %s
   AND m.trend_types && ARRAY['NEW', 'RISING', 'CURRENT']::varchar[]
 ORDER BY m.mention_rank NULLS LAST, k.id
"""


# contents.url 은 UNIQUE지만 조회 이후에도 URL로 한 번 더 중복을 제거한다. 향후 관계 테이블의
# 형태가 바뀌거나 테스트 대역이 중복을 돌려줘도 같은 기사를 AI에 두 번 보내지 않기 위해서다.
RELATED_ARTICLES_SQL = """
SELECT c.id, c.title, c.source, c.url, c.published_at, c.body_object_key
  FROM keyword_contents kc
  JOIN contents c ON c.id = kc.content_id
 WHERE kc.keyword_id = %s
   AND c.body_object_key IS NOT NULL
   AND c.published_at >= %s
   AND c.published_at < %s
 ORDER BY c.published_at DESC, c.id
 LIMIT %s
"""


@dataclass(frozen=True, slots=True)
class TrendTarget:
    keyword_id: int
    keyword: str
    domain: str
    period: str
    period_start: datetime
    period_end: datetime
    mention_rank: int | None
    trend_types: tuple[str, ...] = ()
    mention_count: int = 0
    previous_mention_count: int = 0
    growth_amount: int = 0
    growth_rate: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ArticleReference:
    content_id: int
    title: str
    source: str
    url: str
    published_at: datetime
    body_object_key: str


@dataclass(frozen=True, slots=True)
class TrendArticle:
    content_id: int
    title: str
    source: str
    url: str
    published_at: datetime
    body: str


class TrendArticleRepository:
    """서비스 DB에서 기간별 트렌드와 키워드-기사 관계를 읽는다."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def trend_targets(
        self,
        *,
        domain: str,
        period: str,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[TrendTarget, ...]:
        from trendin.spark.io import jdbc

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                TREND_TARGETS_SQL,
                (domain, period, period_start, period_end),
            )
            rows = cur.fetchall()
        return tuple(TrendTarget(*row[:7], tuple(row[7]), *row[8:]) for row in rows)

    def related_articles(
        self,
        keyword_id: int,
        *,
        published_from: datetime,
        published_until: datetime,
    ) -> tuple[ArticleReference, ...]:
        from trendin.spark.io import jdbc

        with jdbc.connection(self._config) as conn, conn.cursor() as cur:
            cur.execute(
                RELATED_ARTICLES_SQL,
                (keyword_id, published_from, published_until, ARTICLE_CANDIDATE_LIMIT),
            )
            rows = cur.fetchall()
        return tuple(ArticleReference(*row) for row in rows)


class CuratedArticleLoader:
    """contents가 가리키는 curated Parquet에서 기사 본문을 URL로 찾는다."""

    def __init__(self, spark: "SparkSession", config: Config) -> None:
        from trendin.spark.normalize.curated import curated_root

        self._spark = spark
        self._root = curated_root(config).rstrip("/")

    def load(self, references: tuple[ArticleReference, ...]) -> tuple[TrendArticle, ...]:
        if not references:
            return ()

        from pyspark.sql import functions as F

        by_url = {article.url: article for article in references}
        paths = sorted({f"{self._root}/{article.body_object_key}" for article in references})
        allowed_pairs = {(article.body_object_key, article.url) for article in references}
        bare_root = re.sub(URI_SCHEME_RE, "", self._root)
        object_key = F.regexp_replace(
            F.regexp_replace(F.input_file_name(), URI_SCHEME_RE, ""),
            f"^{re.escape(bare_root)}/",
            "",
        ).alias("_body_object_key")
        rows = (
            self._spark.read.option("basePath", self._root)
            .parquet(*paths)
            .where(F.col("url").isin(list(by_url)))
            .where(F.col("dup_of").isNull())
            .select("url", "body", object_key)
            .collect()
        )

        bodies = {
            (row["_body_object_key"], row["url"]): row["body"].strip()
            for row in rows
            if (row["_body_object_key"], row["url"]) in allowed_pairs
            and isinstance(row["body"], str)
            and row["body"].strip()
        }
        return tuple(
            TrendArticle(
                content_id=reference.content_id,
                title=reference.title,
                source=reference.source,
                url=reference.url,
                published_at=reference.published_at,
                body=bodies[(reference.body_object_key, reference.url)],
            )
            for reference in references
            if (reference.body_object_key, reference.url) in bodies
        )


def article_window(target: TrendTarget) -> tuple[datetime, datetime]:
    """선택한 지표 기간과 별개로 완료 구간 끝 이전 30일의 기사를 사용한다."""

    return target.period_end - timedelta(days=30), target.period_end


def select_articles(
    articles: tuple[TrendArticle, ...],
    *,
    max_articles: int = MAX_ARTICLES,
    max_body_chars: int = MAX_ARTICLE_BODY_CHARS,
    max_total_body_chars: int = MAX_TOTAL_BODY_CHARS,
) -> tuple[TrendArticle, ...]:
    """중복·빈 본문을 빼고 최신순으로 MVP 입력 한도까지 고른다."""

    selected: list[TrendArticle] = []
    seen_urls: set[str] = set()
    total_chars = 0
    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        body = article.body.strip()
        if not body or article.url in seen_urls:
            continue
        remaining = max_total_body_chars - total_chars
        if remaining <= 0 or len(selected) >= max_articles:
            break
        body = body[: min(max_body_chars, remaining)].rstrip()
        if not body:
            continue
        selected.append(
            TrendArticle(
                content_id=article.content_id,
                title=article.title,
                source=article.source,
                url=article.url,
                published_at=article.published_at,
                body=body,
            )
        )
        seen_urls.add(article.url)
        total_chars += len(body)
    return tuple(selected)


def build_analysis_input(target: TrendTarget, articles: tuple[TrendArticle, ...]) -> str:
    """기사의 현재 보유 필드만 사용해 TrendAnalyzer의 사용자 입력을 만든다."""

    growth_rate = (
        f"{target.growth_rate}%" if target.growth_rate is not None else "확인 불가"
    )
    sections = [
        f"트렌드 키워드: {target.keyword}",
        f"지표 기간: {target.period} ({target.period_start.isoformat()} ~ "
        f"{target.period_end.isoformat()})",
        f"트렌드 유형: {', '.join(target.trend_types)}",
        f"언급량: {target.mention_count}",
        f"직전 기간 언급량: {target.previous_mention_count}",
        f"언급 증가량: {target.growth_amount}",
        f"증가율: {growth_rate}",
        f"기사 범위: 최근 30일 ({article_window(target)[0].isoformat()} ~ "
        f"{target.period_end.isoformat()})",
        "아래 기사만 근거로 분석한다.",
    ]
    for index, article in enumerate(articles, start=1):
        sections.append(
            "\n".join(
                (
                    f"[기사 {index}]",
                    f"제목: {article.title}",
                    f"출처: {article.source}",
                    f"게시일: {article.published_at.isoformat()}",
                    f"URL: {article.url}",
                    "내용:",
                    article.body,
                )
            )
        )
    return "\n\n".join(sections)


def input_fingerprint(target: TrendTarget, articles: tuple[TrendArticle, ...]) -> str:
    """프롬프트 버전·유형·실제 AI 입력 기사만 해시한다.

    지표 수치만 변한 경우 재호출하지 않지만, 화면 문장을 바꾸는 프롬프트가 바뀌면 재분석한다.
    """

    payload = {
        "prompt_version": PROMPT_VERSION,
        "keyword_id": target.keyword_id,
        "period": target.period,
        "trend_types": sorted(set(target.trend_types)),
        "articles": [
            {
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "published_at": article.published_at.isoformat(),
                "body": article.body,
            }
            for article in articles
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
