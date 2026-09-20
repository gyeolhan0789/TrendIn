"""dev 도메인의 DAG 태스크 경로 (S15P21A102-165).

`fashion/test_runner.py` 와 같은 모양이다 — 세션에 저장해 둔 Algolia 응답을 끼워 발견부터
장부 기록까지 Airflow 없이 돌린다(README 규약 12).
"""

from datetime import datetime, timezone

import httpx

from trendin.common.collect.doubles import InMemoryObjectStore
from trendin.common.collect.ledger import InMemoryLedger
from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.dev.collect import runner

# 고정 자료를 받은 시각. 응답의 `params` 에 찍힌 창의 끝이다.
MEASURED_AT = datetime.fromtimestamp(1789360407, timezone.utc)


def run_kwargs(body: bytes, clock):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"Content-Type": "application/json"})

    def session_factory(**kwargs):
        return CollectSession(
            transport=httpx.MockTransport(handler), clock=clock, sleep=clock.sleep, **kwargs
        )

    return dict(
        ledger=InMemoryLedger(),
        store=InMemoryObjectStore(),
        validators=InMemoryValidatorStore(),
        session_factory=session_factory,
        now=lambda: MEASURED_AT,
    )


def test_소스_키는_hn_하나다():
    assert runner.SOURCE_KEYS == ("hn",)


def test_hn_을_발견부터_장부_기록까지_돈다(api_bytes, clock):
    kwargs = run_kwargs(api_bytes("hn_search_by_date.json"), clock)
    outcome = runner.collect("hn", **kwargs)

    assert outcome.source == "hn"
    assert outcome.domain == "dev"
    assert outcome.discovered == 4
    assert outcome.stored == 4
    assert outcome.failures == ()
    store, ledger = kwargs["store"], kwargs["ledger"]
    assert sorted(store.objects) == sorted(
        [
            "dev/hn/api/2026/09/14/49692009/raw.json",
            "dev/hn/api/2026/09/14/49692009/article.json",
            "dev/hn/api/2026/09/14/49691998/raw.json",
            "dev/hn/api/2026/09/14/49691998/article.json",
            "dev/hn/api/2026/09/14/49691859/raw.json",
            "dev/hn/api/2026/09/14/49691859/article.json",
            "dev/hn/api/2026/09/14/49691343/raw.json",
            "dev/hn/api/2026/09/14/49691343/article.json",
        ]
    )
    assert len(ledger.rows("dev")) == 4


def test_두_번_돌려도_장부와_객체가_안_는다(api_bytes, clock):
    """6시간 창은 매 실행 겹친다. 겹친 글은 장부가 거른다(불변식 12)."""
    kwargs = run_kwargs(api_bytes("hn_search_by_date.json"), clock)
    runner.collect("hn", **kwargs)
    objects = dict(kwargs["store"].objects)
    second = runner.collect("hn", **kwargs)

    assert second.stored == 0
    assert second.skipped == 4
    assert kwargs["store"].objects == objects
