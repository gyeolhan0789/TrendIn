"""Top5 기사 기반 분석 실행과 부분 실패 격리 테스트."""

from datetime import datetime, timezone

from trendin.ai.analyzer import TrendAnalysis
from trendin.ai.articles import ArticleReference, TrendArticle, TrendTarget
from trendin.ai.runner import TopTrendAnalysisRunner

UTC = timezone.utc
START = datetime(2026, 9, 8, tzinfo=UTC)
END = datetime(2026, 9, 15, tzinfo=UTC)


def target(keyword_id, keyword, rank):
    return TrendTarget(keyword_id, keyword, "FASHION", "7D", START, END, rank)


def reference(keyword_id):
    return ArticleReference(
        keyword_id,
        f"기사 {keyword_id}",
        "vogue",
        f"https://example.test/{keyword_id}",
        END,
        f"part-{keyword_id}.parquet",
    )


class StubRepository:
    def __init__(self):
        self.article_queries = []
        self.targets = (
            target(1, "기사없음", 1),
            target(2, "분석성공", 2),
            target(3, "분석실패", 3),
            target(4, "실패뒤성공", 4),
        )

    def top_trends(self, **kwargs):
        self.query = kwargs
        return self.targets

    def related_articles(self, keyword_id, **kwargs):
        self.article_queries.append((keyword_id, kwargs))
        return () if keyword_id == 1 else (reference(keyword_id),)


class StubLoader:
    def load(self, references):
        return tuple(
            TrendArticle(
                item.content_id,
                item.title,
                item.source,
                item.url,
                item.published_at,
                "브랜드 신제품 출시와 관련 스타일링 소개 내용",
            )
            for item in references
        )


class StubAnalyzer:
    def __init__(self):
        self.inputs = []

    def analyze(self, input_text):
        self.inputs.append(input_text)
        if "트렌드 키워드: 분석실패" in input_text:
            raise RuntimeError("GMS 일시 실패")
        return TrendAnalysis(description="설명", summary="요약", reason="이유")


def test_기사가_없으면_AI를_호출하지_않고_각_트렌드_실패를_격리한다():
    repository = StubRepository()
    analyzer = StubAnalyzer()
    outcomes = TopTrendAnalysisRunner(repository, StubLoader(), analyzer).run(
        domain="FASHION", period="7D", period_start=START, period_end=END
    )

    assert repository.query == {
        "domain": "FASHION",
        "period": "7D",
        "period_start": START,
        "period_end": END,
    }
    assert outcomes[0].skipped is True
    assert outcomes[0].article_count == 0
    assert outcomes[1].analysis is not None
    assert outcomes[2].analysis is None
    assert outcomes[2].error == "RuntimeError: GMS 일시 실패"
    assert outcomes[2].article_count == 1
    assert outcomes[3].analysis is not None
    assert len(analyzer.inputs) == 3
    assert repository.article_queries[0] == (
        1,
        {"published_from": START, "published_until": END},
    )


class FailingArticleRepository(StubRepository):
    def related_articles(self, keyword_id, **kwargs):
        if keyword_id == 2:
            raise RuntimeError("기사 조회 실패")
        return super().related_articles(keyword_id, **kwargs)


def test_기사_조회_실패도_해당_트렌드에만_남긴다():
    outcomes = TopTrendAnalysisRunner(
        FailingArticleRepository(), StubLoader(), StubAnalyzer()
    ).run(domain="FASHION", period="7D", period_start=START, period_end=END)

    assert outcomes[1].error == "RuntimeError: 기사 조회 실패"
    assert outcomes[3].analysis is not None
