"""수집 실행 흐름 (설계 문서 #4, S15P21A102-167).

여기서 지키는 것: 장부가 발견과 취득 사이에서 거른다, 저장이 확인된 뒤에만 장부에 적는다,
기사 하나가 깨져도 나머지는 간다, 재시도하면 안 되는 실패는 올라간다, 발급은 미발급 행을
전부 보고 발행 뒤에 장부를 적는다.
"""

from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import Candidate, DiscoverResult, Failure, SourceDef
from trendin.common.collect.flow import (
    SourceOutcome,
    SourceStatus,
    collect_source,
    outcomes_from_xcom,
    publish_pending,
    publish_summaries,
    run_id_of,
    source_statuses,
)
from trendin.common.collect.keys import raw_key
from trendin.common.collect.ledger import InMemoryLedger
from trendin.common.collect.session import HostBlocked

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)

SOURCE = SourceDef(
    key="vogue",
    domain="fashion",
    route="rss",
    discover_url="https://www.vogue.co.kr/category/fashion/feed/",
    allowed_url_prefixes=("https://www.vogue.co.kr/",),
)


class FakeStore:
    """`ObjectStore` 대역. 넣은 것만 있다고 답한다."""

    def __init__(self, swallow: set[str] | None = None) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self._swallow = swallow or set()  # put 은 받되 없는 척하는 키 (저장 확인 실패 재현)

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self.objects[key] = (body, content_type)

    def exists(self, key: str) -> bool:
        return key in self.objects and key not in self._swallow


class FakePublisher:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.flushes = 0

    def publish(self, key: str, value: dict) -> None:
        self.sent.append((key, value))

    def flush(self) -> None:
        self.flushes += 1


def make_article(article_id: str, *, members_only: bool = False) -> Article:
    published = datetime(2026, 9, 3, 10, 0, tzinfo=KST)
    return Article(
        domain=SOURCE.domain,
        source=SOURCE.key,
        route=SOURCE.route,
        article_id=article_id,
        url=f"https://www.vogue.co.kr/{article_id}/",
        title=f"제목 {article_id}",
        published_at=published,
        collected_at=NOW,
        raw_key=(
            None
            if members_only
            else raw_key(SOURCE.domain, SOURCE.key, SOURCE.route, published, article_id)
        ),
        content_sha256=None if members_only else "c" * 64,
        members_only=members_only or None,
    )


class FakeAdapter:
    """후보를 주는 대로 내놓는 어댑터. `broken` 에 든 id 는 취득에서 터진다."""

    def __init__(self, ids, *, broken=(), raises=None, members=()) -> None:
        self.source = SOURCE
        self._ids = list(ids)
        self._broken = set(broken)
        self._raises = raises
        self._members = set(members)
        self.materialized: list[str] = []

    def discover(self, page=None) -> DiscoverResult:
        if self._raises is not None:
            raise self._raises
        return DiscoverResult(
            candidates=[
                Candidate(
                    source=SOURCE.key,
                    article_id=aid,
                    url=f"https://www.vogue.co.kr/{aid}/",
                    raw=b"<item/>",
                    raw_ext="xml",
                    collected_at=NOW,
                )
                for aid in self._ids
            ],
            failures=[Failure(source=SOURCE.key, stage="discover", ref="bad", reason="깨진 item")],
        )

    def materialize(self, candidate: Candidate):
        self.materialized.append(candidate.article_id)
        if candidate.article_id in self._broken:
            raise ValueError("발행일이 없다")
        return b"<item/>", make_article(
            candidate.article_id, members_only=candidate.article_id in self._members
        )


# --- 수집 ------------------------------------------------------------------


def test_장부에_있는_기사는_기사_페이지를_받지_않는다():
    """불변식 12 — 다시 받지도 저장하지도 않는다. 거르는 자리는 취득 **앞**이다."""
    ledger = InMemoryLedger()
    store = FakeStore()
    adapter = FakeAdapter(["1", "2"])
    collect_source(adapter, ledger=ledger, store=store)

    again = FakeAdapter(["1", "2", "3"])
    outcome = collect_source(again, ledger=ledger, store=store)

    assert again.materialized == ["3"]  # 이미 받은 둘은 요청조차 안 갔다
    assert outcome.stored == 1
    assert outcome.skipped == 2


def test_raw_와_article_json_을_둘_다_쓴다():
    store = FakeStore()
    collect_source(FakeAdapter(["1"]), ledger=InMemoryLedger(), store=store)
    keys = sorted(store.objects)
    assert keys == [
        "fashion/vogue/rss/2026/09/03/1/article.json",
        "fashion/vogue/rss/2026/09/03/1/raw.xml",
    ]


def test_회원_전용은_raw_를_쓰지_않는다():
    """불변식 2 — HTML 에 본문이 실려 와도 저장하지 않는다."""
    store = FakeStore()
    collect_source(FakeAdapter(["1"], members=["1"]), ledger=InMemoryLedger(), store=store)
    assert list(store.objects) == ["fashion/vogue/rss/2026/09/03/1/article.json"]


def test_저장이_확인_안_되면_장부에_적지_않는다():
    """불변식 5 — 소비자가 키로 읽었을 때 반드시 있어야 한다."""
    ledger = InMemoryLedger()
    store = FakeStore(swallow={"fashion/vogue/rss/2026/09/03/1/article.json"})
    outcome = collect_source(FakeAdapter(["1"]), ledger=ledger, store=store)

    assert outcome.stored == 0
    assert ledger.pending("fashion") == []
    assert outcome.failed == 2  # 저장 확인 1건 + 이 대역이 늘 내는 발견 실패 1건


def test_기사_하나가_깨져도_나머지는_간다():
    """불변식 9 의 실패 단위는 기사다."""
    outcome = collect_source(
        FakeAdapter(["1", "2", "3"], broken=["2"]), ledger=InMemoryLedger(), store=FakeStore()
    )
    assert outcome.stored == 2
    assert outcome.failed == 2  # 취득 1건 + 발견 1건


def test_재시도하면_안_되는_실패는_그대로_올라간다():
    """403·429 를 받은 뒤 5분 뒤에 다시 치면 불변식 2 를 어긴다."""
    with pytest.raises(HostBlocked):
        collect_source(
            FakeAdapter([], raises=HostBlocked("429 를 받았다")),
            ledger=InMemoryLedger(),
            store=FakeStore(),
        )


def test_같은_구간을_두_번_돌려도_키와_행이_안_는다():
    """불변식 7 — `(source, article_id)` 하나는 키 하나, 장부 행 하나."""
    ledger = InMemoryLedger()
    store = FakeStore()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)
    before = dict(store.objects)
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)

    assert store.objects == before
    assert len(ledger.pending("fashion")) == 2


# --- 발급 ------------------------------------------------------------------


def test_발급은_미발급_행을_전부_보고_발행_뒤에_장부를_적는다():
    ledger = InMemoryLedger()
    store = FakeStore()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)

    publisher = FakePublisher()
    sent = publish_pending(
        ledger=ledger, publisher=publisher, bucket="raw-data", domain="fashion", now=NOW
    )

    assert sent == 2
    assert publisher.flushes == 1  # 한 번에 모아 비운다
    assert [k for k, _ in publisher.sent] == ["vogue", "vogue"]  # message key 는 source_id
    assert ledger.pending("fashion") == []  # 다 나갔으니 남은 게 없다


def test_두_번째_발급은_아무것도_내지_않는다():
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=FakeStore())
    publisher = FakePublisher()
    for _ in range(2):
        publish_pending(
            ledger=ledger, publisher=publisher, bucket="raw-data", domain="fashion", now=NOW
        )
    assert len(publisher.sent) == 1


def test_발행이_실패하면_장부를_적지_않는다():
    """적어 버리면 토픽엔 없는데 나갔다고 적힌 기사가 생긴다."""

    class Broken(FakePublisher):
        def flush(self) -> None:
            raise RuntimeError("브로커가 안 받았다")

    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=FakeStore())
    with pytest.raises(RuntimeError):
        publish_pending(
            ledger=ledger, publisher=Broken(), bucket="raw-data", domain="fashion", now=NOW
        )
    assert len(ledger.pending("fashion")) == 1  # 다음 실행이 이어 낸다


def test_다른_도메인_행은_건드리지_않는다():
    """발급이 DAG 마다 하나씩이라 도메인으로 자르지 않으면 dev DAG 이 fashion 행을 낸다."""
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=FakeStore())
    publisher = FakePublisher()
    sent = publish_pending(
        ledger=ledger, publisher=publisher, bucket="raw-data", domain="dev", now=NOW
    )
    assert sent == 0
    assert len(ledger.pending("fashion")) == 1


def test_요약_이벤트는_0건이어도_나가고_죽은_소스는_failed_로_나간다():
    publisher = FakePublisher()
    sent = publish_summaries(
        publisher=publisher,
        bucket="raw-data",
        run_id="20260903T100000",
        logical_date=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        statuses=[
            SourceStatus(source="vogue", domain="fashion", status="success"),
            SourceStatus(
                source="wkorea", domain="fashion", status="failed", failure_reason="죽었다"
            ),
        ],
        counts={"vogue": 0},
    )
    assert sent == 2
    by_source = {v["source_id"]: v for _, v in publisher.sent}
    assert by_source["vogue"]["status"] == "success"
    assert by_source["vogue"]["record_count"] == 0  # 0건도 낸다 (팀 발행 규약 4)
    assert by_source["wkorea"]["status"] == "failed"
    assert by_source["wkorea"]["failure_reason"]


# --- DAG 이 들고 있던 판정 ---------------------------------------------------
# 규약 1 대로 DAG 파일에서 내려온 것들. 내려왔으니 Airflow 없이 테스트된다(규약 12).


def test_run_id_는_KST_로_찍는다():
    """팀 계약: logical date 파생 `yyyyMMddTHHmmss` (KST)."""
    assert run_id_of(datetime(2026, 9, 7, 4, 10, 10, tzinfo=timezone.utc)) == "20260907T131010"


def test_XCom_에_안_돌아온_소스가_죽은_소스다():
    """수집 태스크가 재시도까지 소진해 죽으면 그 인스턴스는 XCom 을 안 남긴다."""
    statuses = source_statuses(
        ["vogue", "wkorea"],
        [SourceOutcome(source="vogue", domain="fashion", stored=3)],
        lambda key: "fashion",
    )
    by_source = {s.source: s for s in statuses}
    assert by_source["vogue"].status == "success"
    assert by_source["wkorea"].status == "failed"
    assert by_source["wkorea"].failure_reason  # 팀 발행 규약 5 — 이유를 채운다


def test_매핑이_한_건이면_dict_하나로_온다():
    one = SourceOutcome(source="vogue", domain="fashion", stored=1).to_dict()
    assert [o.source for o in outcomes_from_xcom(one)] == ["vogue"]
    assert [o.source for o in outcomes_from_xcom([one])] == ["vogue"]
    assert outcomes_from_xcom(None) == []


def test_XCom_에_예외_문자열을_싣지_않는다():
    """규약 4 — XCom 엔 ID·건수만. 예외 문자열은 길이도 내용도 예측이 안 된다."""
    outcome = collect_source(
        FakeAdapter(["1", "2"], broken=["2"]), ledger=InMemoryLedger(), store=FakeStore()
    )
    payload = outcome.to_dict()
    assert payload["failed"] == 2
    assert all(isinstance(v, (str, int, bool)) for v in payload.values())
    assert "발행일이 없다" not in repr(payload)
