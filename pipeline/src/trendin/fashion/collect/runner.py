"""소스 키 하나를 실행 흐름에 태우는 배선 (fashion 도메인, S15P21A102-167).

DAG 파일이 부르는 건 여기 `collect` 하나다. 세션을 열고 route 에 맞는 어댑터를 골라
공통 실행 흐름에 넘긴다. 소스가 하나 늘어도 이 파일은 그대로다 — 소스별 차이는
`SourceDef` 의 열로 흡수된다(설계 문서 #1).
"""

from __future__ import annotations

from trendin.common.collect.contracts import SourceAdapter, ValidatorStore
from trendin.common.collect.flow import SourceOutcome, collect_source
from trendin.common.collect.ledger import Ledger
from trendin.common.collect.session import CollectSession
from trendin.common.collect.sinks import ObjectStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.listing import ListingAdapter
from trendin.fashion.collect.rss import RssAdapter

# route 하나에 어댑터 하나다 (#5.1 은 소스당 route 도 하나로 고정한다).
ADAPTERS = {"rss": RssAdapter, "listing": ListingAdapter}

SOURCE_KEYS = tuple(sorted(sources.BY_KEY))


def build_adapter(source, session) -> SourceAdapter:
    try:
        return ADAPTERS[source.route](source, session)
    except KeyError:
        raise KeyError(f"어댑터가 없는 route 다: {source.route!r}") from None


def collect(
    source_key: str,
    *,
    ledger: Ledger,
    store: ObjectStore,
    validators: ValidatorStore,
    session_factory=CollectSession,
) -> SourceOutcome:
    """소스 하나를 발견부터 장부 기록까지 돈다. 발급은 여기 없다.

    세션이 소스마다 따로 열리는 게 호스트 간격의 단위다. 소스↔호스트가 1:1 이라
    소스당 태스크 하나면 같은 호스트를 동시에 치는 일이 생기지 않는다(불변식 4).

    `session_factory` 는 테스트가 고정 응답을 끼우는 자리다. DAG 이 부르는 바로 이 경로를
    Airflow 없이 검증하라는 게 README 규약 12 다.
    """
    source = sources.get(source_key)
    with session_factory(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=validators,
    ) as session:
        adapter = build_adapter(source, session)
        return collect_source(adapter, ledger=ledger, store=store)
