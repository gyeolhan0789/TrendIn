"""Hacker News 구간 백필 (S15P21A102-165).

주기 실행은 최근 6시간만 본다. 첫 채움과 멈춘 구간 메우기는 이 명령이 시각 구간으로 받는다.
주기 실행과 **같은** 발견(`discover_range`)·저장 루프(`flow.store_candidates`)를 탄다.
"""

from datetime import datetime, timezone

import httpx
import pytest

from trendin.common.collect.doubles import InMemoryObjectStore
from trendin.common.collect.ledger import InMemoryLedger
from trendin.common.collect.session import CollectSession
from trendin.dev.collect import backfill, sources
from trendin.dev.collect.hackernews import HackerNewsAdapter

START = 1_789_000_000
HOUR = 3600


def at(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, timezone.utc)


def walk(algolia, clock, *, since, until, ledger, store):
    source = sources.get("hn")
    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        transport=httpx.MockTransport(algolia),
        clock=clock,
        sleep=clock.sleep,
    ) as session:
        return backfill.walk_range(
            HackerNewsAdapter(source, session), since=since, until=until, ledger=ledger, store=store
        )


def test_구간을_6시간씩_돌며_전부_저장한다(clock, fake_algolia):
    # 20시간에 걸쳐 한 시간에 한 건.
    algolia = fake_algolia([START + h * HOUR for h in range(20)])
    ledger, store = InMemoryLedger(), InMemoryObjectStore()

    total, stored = walk(
        algolia, clock, since=at(START), until=at(START + 20 * HOUR), ledger=ledger, store=store
    )

    assert (total, stored) == (20, 20)
    assert [(s - START) // HOUR for s, _u, _n in algolia.windows] == [0, 6, 12, 18]
    assert algolia.windows[-1][1] == START + 20 * HOUR  # 마지막 조각은 until 에서 끊긴다
    # 발급은 하지 않는다. 다음 주기 실행의 발급 태스크가 미발급 행을 이어 낸다.
    assert len(ledger.rows("dev")) == 20


def test_이미_받은_구간과_겹쳐도_장부에_없는_것만_저장한다(clock, fake_algolia):
    """멈춘 구간 메우기 — 앞뒤로 이미 받은 글이 있는 구간을 넉넉히 줘도 된다."""
    algolia = fake_algolia([START + h * HOUR for h in range(12)])
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    walk(algolia, clock, since=at(START), until=at(START + 6 * HOUR), ledger=ledger, store=store)

    total, stored = walk(
        algolia, clock, since=at(START), until=at(START + 12 * HOUR), ledger=ledger, store=store
    )

    assert (total, stored) == (6, 6)
    assert len(store.objects) == 12 * 2


def test_장부_없이_훑으면_저장하지_않고_센다(clock, fake_algolia):
    algolia = fake_algolia([START + h * HOUR for h in range(3)])

    total, stored = walk(
        algolia, clock, since=at(START), until=at(START + 3 * HOUR), ledger=None, store=None
    )

    assert (total, stored) == (3, 0)


def test_since_는_필수이고_until_보다_앞서야_한다():
    with pytest.raises(SystemExit):
        backfill.main(["hn"])
    with pytest.raises(SystemExit) as exc:
        backfill.main(
            ["hn", "--since", "2026-09-14T00:00+09:00", "--until", "2026-09-13T00:00+09:00"]
        )
    assert "since" in str(exc.value)


def test_오프셋_없는_시각은_받지_않는다():
    """KST 로 읽을지 UTC 로 읽을지 9시간이 갈린다. 추측하지 않는다."""
    with pytest.raises(SystemExit):
        backfill.main(["hn", "--since", "2026-08-03T00:00"])


def test_구간_백필은_api_소스만_받는다():
    assert backfill.BACKFILLABLE == ("hn",)


def test_6주보다_긴_구간은_받지_않는다(monkeypatch):
    """아카이브 전량 백필은 범위 밖이다(설계 문서 #1). `--since` 를 멀리 잘못 줘도 돌지 않는다.

    6주를 넘는 공백을 메울 일이 생기면 구간을 나눠 두 번 돌린다 — 장부가 겹친 글을 거른다.
    """

    def no_network(**_kwargs):
        raise AssertionError("인자 검사에서 멈춰야 한다 — 세션을 열면 실제 Algolia 를 친다")

    monkeypatch.setattr(backfill, "CollectSession", no_network)
    with pytest.raises(SystemExit) as exc:
        backfill.main(
            ["hn", "--since", "2026-07-01T00:00+09:00", "--until", "2026-08-12T00:00:01+09:00"]
        )
    assert "6주" in str(exc.value)
