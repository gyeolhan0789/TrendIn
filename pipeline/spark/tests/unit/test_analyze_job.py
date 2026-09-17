"""AI 분석 Job의 완료 구간 및 도메인별 실행 배선 테스트."""

from argparse import Namespace
from datetime import datetime
from types import SimpleNamespace

import analyze

from trendin.spark.common.config import Config, ConfigError


def test_완료된_7D_구간을_각_도메인의_분석_저장_runner에_전달한다(monkeypatch):
    calls = []
    repository = object()
    loader = object()
    store = object()

    class Runner:
        def __init__(self, received_repository, received_loader, *, store):
            assert received_repository is repository
            assert received_loader is loader
            assert store is saved_store

        def run(self, **kwargs):
            calls.append(kwargs)
            return (SimpleNamespace(analysis=object(), skipped=False),)

    saved_store = store
    monkeypatch.setattr(analyze, "TrendArticleRepository", lambda config: repository)
    monkeypatch.setattr(analyze, "CuratedArticleLoader", lambda spark, config: loader)
    monkeypatch.setattr(analyze, "TrendAnalysisStore", lambda config: saved_store)
    monkeypatch.setattr(analyze, "TopTrendAnalysisRunner", Runner)
    config = Config(
        {
            "aggregate": {"reference_day_offset": 1},
            "extract": {"domains": {"dev": {}, "fashion": {}}},
        },
        profile="local",
    )

    analyze.run(object(), config, Namespace(date="2026-09-16", period="7D"))

    assert calls == [
        {
            "domain": domain,
            "period": "7D",
            "period_start": datetime.fromisoformat("2026-09-09T00:00:00+09:00"),
            "period_end": datetime.fromisoformat("2026-09-16T00:00:00+09:00"),
        }
        for domain in ("DEV", "FASHION")
    ]


def test_분석_도메인_설정이_없으면_시작하지_않는다():
    config = Config({"extract": {"domains": {}}}, profile="local")

    try:
        analyze.run(object(), config, Namespace(date="2026-09-16", period="7D"))
    except ConfigError as error:
        assert "extract.domains" in str(error)
    else:
        raise AssertionError("분석할 도메인이 없으면 ConfigError가 필요하다")


def test_기간을_지정하지_않으면_세_기간을_각각_분석한다(monkeypatch):
    calls = []

    class Runner:
        def __init__(self, *_args, **_kwargs):
            pass

        def run(self, **kwargs):
            calls.append(kwargs)
            return ()

    monkeypatch.setattr(analyze, "TrendArticleRepository", lambda config: object())
    monkeypatch.setattr(analyze, "CuratedArticleLoader", lambda spark, config: object())
    monkeypatch.setattr(analyze, "TrendAnalysisStore", lambda config: object())
    monkeypatch.setattr(analyze, "TopTrendAnalysisRunner", Runner)
    config = Config(
        {"aggregate": {"reference_day_offset": 1}, "extract": {"domains": {"fashion": {}}}},
        profile="local",
    )

    analyze.run(object(), config, Namespace(date="2026-09-16", period=None))

    assert [call["period"] for call in calls] == ["24H", "7D", "30D"]
    assert all(call["domain"] == "FASHION" for call in calls)
