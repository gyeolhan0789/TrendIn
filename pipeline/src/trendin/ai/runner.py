"""Top5 트렌드를 기사 기반으로 독립 분석한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from trendin.ai.analyzer import TrendAnalysis, TrendAnalyzer
from trendin.ai.articles import (
    ArticleReference,
    TrendArticle,
    TrendTarget,
    article_window,
    build_analysis_input,
    select_articles,
)


class ArticleRepository(Protocol):
    def top_trends(
        self,
        *,
        domain: str,
        period: str,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[TrendTarget, ...]: ...

    def related_articles(
        self,
        keyword_id: int,
        *,
        published_from: datetime,
        published_until: datetime,
    ) -> tuple[ArticleReference, ...]: ...


class ArticleLoader(Protocol):
    def load(self, references: tuple[ArticleReference, ...]) -> tuple[TrendArticle, ...]: ...


@dataclass(frozen=True, slots=True)
class TrendAnalysisOutcome:
    """트렌드 하나의 분석 결과. 저장은 Jira #272가 담당한다."""

    target: TrendTarget
    analysis: TrendAnalysis | None
    article_count: int
    error: str | None = None

    @property
    def skipped(self) -> bool:
        return self.analysis is None and self.error is None


class TopTrendAnalysisRunner:
    """Top5 각각을 독립 처리해 부분 실패에도 나머지 결과를 돌려준다."""

    def __init__(
        self,
        repository: ArticleRepository,
        loader: ArticleLoader,
        analyzer: TrendAnalyzer | None = None,
    ) -> None:
        self._repository = repository
        self._loader = loader
        self._analyzer = analyzer or TrendAnalyzer()

    def run(
        self,
        *,
        domain: str,
        period: str,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[TrendAnalysisOutcome, ...]:
        targets = self._repository.top_trends(
            domain=domain,
            period=period,
            period_start=period_start,
            period_end=period_end,
        )
        outcomes: list[TrendAnalysisOutcome] = []
        for target in targets:
            article_count = 0
            try:
                published_from, published_until = article_window(target)
                references = self._repository.related_articles(
                    target.keyword_id,
                    published_from=published_from,
                    published_until=published_until,
                )
                articles = select_articles(self._loader.load(references))
                if not articles:
                    outcomes.append(
                        TrendAnalysisOutcome(target=target, analysis=None, article_count=0)
                    )
                    continue
                article_count = len(articles)
                analysis = self._analyzer.analyze(build_analysis_input(target, articles))
                outcomes.append(
                    TrendAnalysisOutcome(
                        target=target,
                        analysis=analysis,
                        article_count=article_count,
                    )
                )
            except Exception as exc:  # 트렌드 하나의 외부 조회·AI 실패를 격리한다.
                outcomes.append(
                    TrendAnalysisOutcome(
                        target=target,
                        analysis=None,
                        article_count=article_count,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
        return tuple(outcomes)
