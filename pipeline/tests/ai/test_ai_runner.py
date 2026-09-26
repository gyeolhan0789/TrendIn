"""기간별 기사 기반 분석 실행과 부분 실패 격리 테스트."""

from dataclasses import replace
from datetime import datetime, timezone

from trendin.ai.analyzer import TrendAnalysis
from trendin.ai.articles import ArticleReference, TrendArticle, TrendTarget
from trendin.ai.runner import TopTrendAnalysisRunner

UTC = timezone.utc
START = datetime(2026, 9, 8, tzinfo=UTC)
END = datetime(2026, 9, 15, tzinfo=UTC)


def target(keyword_id, keyword, rank):
    return TrendTarget(keyword_id, keyword, "FASHION", "7D", START, END, rank,
                       ("NEW", "RISING"), 120, 40, 80)


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
        self.fallback_queries = []
        self.targets = (
            target(1, "기사없음", 1),
            target(2, "분석성공", 2),
            target(3, "분석실패", 3),
            target(4, "실패뒤성공", 4),
        )

    def trend_targets(self, **kwargs):
        self.query = kwargs
        return self.targets

    def related_articles(self, keyword_id, **kwargs):
        self.article_queries.append((keyword_id, kwargs))
        return () if keyword_id == 1 else (reference(keyword_id),)

    def counted_articles(self, keyword_id, **kwargs):
        self.fallback_queries.append((keyword_id, kwargs))
        return ()


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


class StubStore:
    def __init__(self, *, fail_keyword_id=None):
        self.saved = []
        self.fail_keyword_id = fail_keyword_id
        self.fingerprints = {}

    def is_current(self, target, fingerprint):
        return self.fingerprints.get((target.keyword_id, target.period)) == fingerprint

    def save(self, target, analysis, fingerprint):
        if target.keyword_id == self.fail_keyword_id:
            raise RuntimeError("DB 저장 실패")
        self.saved.append((target.keyword_id, analysis, fingerprint))
        self.fingerprints[(target.keyword_id, target.period)] = fingerprint
        return target.keyword_id


def test_기사가_없으면_AI를_호출하지_않고_각_트렌드_실패를_격리한다():
    repository = StubRepository()
    analyzer = StubAnalyzer()
    store = StubStore()
    outcomes = TopTrendAnalysisRunner(
        repository, StubLoader(), analyzer, store=store
    ).run(
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
    assert [keyword_id for keyword_id, _, _ in store.saved] == [2, 4]
    assert repository.article_queries[0] == (
        1,
        {"published_from": START, "published_until": END},
    )
    assert [keyword_id for keyword_id, _ in repository.fallback_queries] == [1]


def test_기존_기사에_사용할_본문이_없을_때만_집계_문서로_분석한다():
    repository = StubRepository()
    repository.targets = (target(1, "대체기사", 1), target(2, "기존기사", 2))

    def counted_articles(keyword_id, **kwargs):
        repository.fallback_queries.append((keyword_id, kwargs))
        return (reference(keyword_id),)

    repository.counted_articles = counted_articles
    analyzer = StubAnalyzer()
    store = StubStore()
    outcomes = TopTrendAnalysisRunner(repository, StubLoader(), analyzer, store).run(
        domain="FASHION", period="7D", period_start=START, period_end=END
    )

    assert [outcome.article_count for outcome in outcomes] == [1, 1]
    assert [keyword_id for keyword_id, _, _ in store.saved] == [1, 2]
    assert repository.fallback_queries == [
        (1, {"published_from": START, "published_until": END})
    ]


def test_연결된_기사가_있어도_본문이_비면_집계_문서로_전환한다():
    repository = StubRepository()
    repository.targets = (target(2, "대체기사", 1),)
    repository.counted_articles = lambda keyword_id, **kwargs: (reference(3),)

    class EmptyOriginalBody(StubLoader):
        def load(self, references):
            return tuple(
                replace(item, body=" " if item.content_id == 2 else "실제 본문")
                for item in super().load(references)
            )

    analyzer = StubAnalyzer()
    outcome = TopTrendAnalysisRunner(
        repository, EmptyOriginalBody(), analyzer, StubStore()
    ).run(domain="FASHION", period="7D", period_start=START, period_end=END)[0]

    assert outcome.article_count == 1
    assert "실제 본문" in analyzer.inputs[0]
    assert "기사 2" not in analyzer.inputs[0]


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


def test_저장_실패도_해당_트렌드에만_남기고_다음_결과를_저장한다():
    repository = StubRepository()
    store = StubStore(fail_keyword_id=2)
    outcomes = TopTrendAnalysisRunner(
        repository, StubLoader(), StubAnalyzer(), store=store
    ).run(domain="FASHION", period="7D", period_start=START, period_end=END)

    assert outcomes[1].analysis is None
    assert outcomes[1].error == "RuntimeError: DB 저장 실패"
    assert outcomes[3].analysis is not None
    assert [keyword_id for keyword_id, _, _ in store.saved] == [4]
    assert [keyword_id for keyword_id, _ in repository.fallback_queries] == [1]


def test_같은_유형과_기사면_재호출하지_않고_수치만_변해도_재사용한다():
    repository = StubRepository()
    repository.targets = (target(2, "분석성공", 2),)
    analyzer = StubAnalyzer()
    store = StubStore()
    runner = TopTrendAnalysisRunner(repository, StubLoader(), analyzer, store)
    kwargs = dict(domain="FASHION", period="7D", period_start=START, period_end=END)

    assert runner.run(**kwargs)[0].analysis is not None
    repository.targets = (replace(repository.targets[0], mention_count=999,
                                  growth_amount=959),)
    assert runner.run(**kwargs)[0].skipped is True
    assert len(analyzer.inputs) == 1
    assert len(store.saved) == 1


def test_유형이나_선택된_기사_본문이_바뀌면_재분석한다():
    repository = StubRepository()
    repository.targets = (target(2, "분석성공", 2),)
    analyzer = StubAnalyzer()
    store = StubStore()

    class ChangingLoader(StubLoader):
        body = "첫 번째 본문"

        def load(self, references):
            return tuple(replace(item, body=self.body) for item in super().load(references))

    loader = ChangingLoader()
    runner = TopTrendAnalysisRunner(repository, loader, analyzer, store)
    kwargs = dict(domain="FASHION", period="7D", period_start=START, period_end=END)

    runner.run(**kwargs)
    repository.targets = (replace(repository.targets[0], trend_types=("RISING",)),)
    runner.run(**kwargs)
    loader.body = "두 번째 본문"
    runner.run(**kwargs)

    assert len(analyzer.inputs) == 3
    assert len(store.saved) == 3


def test_재분석_GMS_실패시_기존_fingerprint를_보존하고_다음_키워드를_계속한다():
    repository = StubRepository()
    repository.targets = (target(2, "첫번째", 1), target(4, "두번째", 2))
    store = StubStore()

    class FailingAnalyzer(StubAnalyzer):
        fail = False

        def analyze(self, input_text):
            if self.fail and "트렌드 키워드: 첫번째" in input_text:
                raise RuntimeError("GMS 실패")
            return super().analyze(input_text)

    class ChangingLoader(StubLoader):
        body = "원래 기사"

        def load(self, references):
            return tuple(replace(item, body=self.body) for item in super().load(references))

    analyzer = FailingAnalyzer()
    loader = ChangingLoader()
    runner = TopTrendAnalysisRunner(repository, loader, analyzer, store)
    kwargs = dict(domain="FASHION", period="7D", period_start=START, period_end=END)
    runner.run(**kwargs)
    original = store.fingerprints[(2, "7D")]

    loader.body = "새 기사"
    analyzer.fail = True
    outcomes = runner.run(**kwargs)

    assert outcomes[0].error == "RuntimeError: GMS 실패"
    assert outcomes[1].analysis is not None
    assert store.fingerprints[(2, "7D")] == original
    assert store.fingerprints[(4, "7D")] != original
