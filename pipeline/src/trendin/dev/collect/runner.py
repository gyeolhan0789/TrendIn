"""소스 키 하나를 실행 흐름에 태우는 배선 (dev 도메인, S15P21A102-165).

`trendin.fashion.collect.runner` 와 같은 모양이다. DAG 파일이 부르는 건 `collect` 하나고,
세션을 열어 route 에 맞는 어댑터를 공통 실행 흐름에 넘긴다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from trendin.common.collect.contracts import SourceAdapter, ValidatorStore
from trendin.common.collect.flow import SourceOutcome, collect_source
from trendin.common.collect.ledger import Ledger
from trendin.common.collect.session import CollectSession
from trendin.common.collect.sinks import ObjectStore
from trendin.dev.collect import sources
from trendin.dev.collect.hackernews import HackerNewsAdapter

ADAPTERS = {"api": HackerNewsAdapter}

SOURCE_KEYS = tuple(sorted(sources.BY_KEY))


def build_adapter(source, session, *, now: Callable[[], datetime] | None = None) -> SourceAdapter:
    try:
        return ADAPTERS[source.route](source, session, now=now)
    except KeyError:
        raise KeyError(f"어댑터가 없는 route 다: {source.route!r}") from None


def collect(
    source_key: str,
    *,
    ledger: Ledger,
    store: ObjectStore,
    validators: ValidatorStore,
    session_factory=CollectSession,
    now: Callable[[], datetime] | None = None,
) -> SourceOutcome:
    """소스 하나를 발견부터 장부 기록까지 돈다. 발급은 여기 없다.

    세션이 소스마다 따로 열리는 게 호스트 간격의 단위다(불변식 4). `session_factory` 는
    테스트가 저장해 둔 응답을 끼우는 자리다 — DAG 이 부르는 바로 이 경로를 Airflow 없이
    검증하라는 게 README 규약 12 다. `now` 도 같은 자리다 — 6시간 창이 벽시계를 따르면
    저장해 둔 응답이 시간이 지나 창 밖으로 밀려난다.
    """
    source = sources.get(source_key)
    with session_factory(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=validators,
    ) as session:
        adapter = build_adapter(source, session, now=now)
        return collect_source(adapter, ledger=ledger, store=store)
