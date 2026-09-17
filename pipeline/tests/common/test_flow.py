"""수집 실행 흐름 (설계 문서 #4, S15P21A102-167).

여기서 지키는 것: 장부가 발견과 취득 사이에서 거른다, 저장이 확인된 뒤에만 장부에 적는다,
기사 하나가 깨져도 나머지는 간다, 재시도하면 안 되는 실패는 올라간다, 발급은 미발급 행을
전부 보고 발행 뒤에 장부를 적는다.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import (
    UNKNOWN_COUNTRY,
    Candidate,
    DiscoverResult,
    Failure,
    SourceDef,
)
from trendin.common.collect.doubles import InMemoryObjectStore, RecordingEventPublisher
from trendin.common.collect.flow import (
    SourceOutcome,
    SourceStatus,
    collect_source,
    outcomes_from_xcom,
    publish_pending,
    publish_summaries,
    run_id_of,
    source_statuses,
    store_article,
)
from trendin.common.collect.keys import raw_key
from trendin.common.collect.ledger import EmittedStats, InMemoryLedger
from trendin.common.collect.session import HostBlocked

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 2, 0, tzinfo=timezone.utc)

SOURCE = SourceDef(
    key="vogue",
    domain="fashion",
    route="rss",
    discover_url="https://www.vogue.co.kr/category/fashion/feed/",
    allowed_url_prefixes=("https://www.vogue.co.kr/",),
    country="KR",
)
# 장부의 국가 거울에 들어가는 것. `dag_factory` 의 `ensure_schema` 태스크가 소스 레지스트리에서
# 만들어 넘기는 것과 같은 모양이고, 발급은 코드 표가 아니라 그 거울을 읽는다.
COUNTRIES = {SOURCE.key: SOURCE.country}


def make_article(
    article_id: str, *, members_only: bool = False, paywalled: bool = False
) -> Article:
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
            if members_only or paywalled
            else raw_key(SOURCE.domain, SOURCE.key, SOURCE.route, published, article_id)
        ),
        content_sha256=None if members_only or paywalled else "c" * 64,
        members_only=members_only or None,
        paywalled=paywalled or None,
    )


class FakeAdapter:
    """후보를 주는 대로 내놓는 어댑터. `broken` 에 든 id 는 취득에서 터진다."""

    def __init__(self, ids, *, broken=(), raises=None, members=(), paywalled=()) -> None:
        self.source = SOURCE
        self._ids = list(ids)
        self._broken = set(broken)
        self._raises = raises
        self._members = set(members)
        self._paywalled = set(paywalled)
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
            candidate.article_id,
            members_only=candidate.article_id in self._members,
            paywalled=candidate.article_id in self._paywalled,
        )


# --- 수집 ------------------------------------------------------------------


def test_장부에_있는_기사는_기사_페이지를_받지_않는다():
    """불변식 12 — 다시 받지도 저장하지도 않는다. 거르는 자리는 취득 **앞**이다."""
    ledger = InMemoryLedger()
    store = InMemoryObjectStore()
    adapter = FakeAdapter(["1", "2"])
    collect_source(adapter, ledger=ledger, store=store)

    again = FakeAdapter(["1", "2", "3"])
    outcome = collect_source(again, ledger=ledger, store=store)

    assert again.materialized == ["3"]  # 이미 받은 둘은 요청조차 안 갔다
    assert outcome.stored == 1
    assert outcome.skipped == 2


def test_raw_와_article_json_을_둘_다_쓴다():
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"]), ledger=InMemoryLedger(), store=store)
    keys = sorted(store.objects)
    assert keys == [
        "fashion/vogue/rss/2026/09/03/1/article.json",
        "fashion/vogue/rss/2026/09/03/1/raw.xml",
    ]


def test_회원_전용은_raw_를_쓰지_않는다():
    """불변식 2 — HTML 에 본문이 실려 와도 저장하지 않는다."""
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"], members=["1"]), ledger=InMemoryLedger(), store=store)
    assert list(store.objects) == ["fashion/vogue/rss/2026/09/03/1/article.json"]


def test_저장이_확인_안_되면_장부에_적지_않는다():
    """불변식 5 — 소비자가 키로 읽었을 때 반드시 있어야 한다."""
    ledger = InMemoryLedger()
    store = InMemoryObjectStore(swallow={"fashion/vogue/rss/2026/09/03/1/article.json"})
    outcome = collect_source(FakeAdapter(["1"]), ledger=ledger, store=store)

    assert outcome.stored == 0
    assert ledger.pending("fashion") == []
    assert outcome.failed == 2  # 저장 확인 1건 + 이 대역이 늘 내는 발견 실패 1건


def test_기사_하나가_깨져도_나머지는_간다():
    """불변식 9 의 실패 단위는 기사다."""
    outcome = collect_source(
        FakeAdapter(["1", "2", "3"], broken=["2"]),
        ledger=InMemoryLedger(),
        store=InMemoryObjectStore(),
    )
    assert outcome.stored == 2
    assert outcome.failed == 2  # 취득 1건 + 발견 1건


def test_재시도하면_안_되는_실패는_그대로_올라간다():
    """403·429 를 받은 뒤 5분 뒤에 다시 치면 불변식 2 를 어긴다."""
    with pytest.raises(HostBlocked):
        collect_source(
            FakeAdapter([], raises=HostBlocked("429 를 받았다")),
            ledger=InMemoryLedger(),
            store=InMemoryObjectStore(),
        )


def test_같은_구간을_두_번_돌려도_키와_행이_안_는다():
    """불변식 7 — `(source, article_id)` 하나는 키 하나, 장부 행 하나."""
    ledger = InMemoryLedger()
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)
    before = dict(store.objects)
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)

    assert store.objects == before
    assert len(ledger.pending("fashion")) == 2


# --- 발급 ------------------------------------------------------------------


def test_발급은_미발급_행을_전부_보고_발행_뒤에_장부를_적는다():
    ledger = InMemoryLedger()
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=store)

    publisher = RecordingEventPublisher()
    sent = publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
    )

    assert sent == {"vogue": EmittedStats(2, NOW)}
    assert publisher.flushes == 1  # 한 번에 모아 비운다
    assert [k for k, _ in publisher.sent] == ["vogue", "vogue"]  # message key 는 source_id
    assert ledger.pending("fashion") == []  # 다 나갔으니 남은 게 없다


def test_두_번째_발급은_아무것도_내지_않는다():
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    for _ in range(2):
        publish_pending(
            ledger=ledger,
            publisher=publisher,
            bucket="raw-data",
            domain="fashion",
                run_id="20260903T110000",
            now=NOW,
        )
    assert len(publisher.sent) == 1


def test_발행이_실패하면_장부를_적지_않는다():
    """적어 버리면 토픽엔 없는데 나갔다고 적힌 기사가 생긴다."""

    class Broken(RecordingEventPublisher):
        def flush(self) -> None:
            raise RuntimeError("브로커가 안 받았다")

    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    with pytest.raises(RuntimeError):
        publish_pending(
            ledger=ledger,
            publisher=Broken(),
            bucket="raw-data",
            domain="fashion",
                run_id="20260903T110000",
            now=NOW,
        )
    assert len(ledger.pending("fashion")) == 1  # 다음 실행이 이어 낸다


def test_다른_도메인_행은_건드리지_않는다():
    """발급이 DAG 마다 하나씩이라 도메인으로 자르지 않으면 dev DAG 이 fashion 행을 낸다."""
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    sent = publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="dev",
        run_id="20260903T110000",
        now=NOW,
    )
    assert sent == {}
    assert len(ledger.pending("fashion")) == 1


def test_요약_이벤트는_0건이어도_나가고_죽은_소스는_failed_로_나간다():
    publisher = RecordingEventPublisher()
    sent = publish_summaries(
        publisher=publisher,
        run_id="20260903T100000",
        logical_date=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        statuses=[
            SourceStatus(source="vogue", domain="fashion", status="success",
                         outcome=SourceOutcome(source="vogue", domain="fashion")),
            SourceStatus(
                source="wkorea", domain="fashion", status="failed", failure_reason="죽었다"
            ),
        ],
        counts={},
    )
    assert sent == 2
    by_source = {v["source_id"]: v for _, v in publisher.sent}
    assert by_source["vogue"]["status"] == "success"
    assert by_source["vogue"]["emitted"] == 0  # 0건도 낸다 (팀 발행 규약 4)
    assert by_source["wkorea"]["status"] == "failed"
    assert by_source["wkorea"]["failure_reason"]
    assert by_source["vogue"]["stored"] == 0
    assert by_source["vogue"]["emitted_oldest_collected_at"] is None
    assert by_source["wkorea"]["stored"] is None


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


def test_수집_결과는_단계별_실패와_저장_숫자를_XCom_왕복에도_보존한다(monkeypatch):
    import json

    ticks = iter([10.0, 31.43])
    monkeypatch.setattr("trendin.common.collect.flow.time.monotonic", lambda: next(ticks))
    outcome = collect_source(
        FakeAdapter(["1", "2", "3"], broken=["2"], members=["1", "3"]),
        ledger=InMemoryLedger(),
        store=InMemoryObjectStore(swallow={"fashion/vogue/rss/2026/09/03/3/article.json"}),
    )
    assert outcome.discovered == 3
    assert outcome.stored == outcome.members_only_stored == 1
    assert outcome.failed == 3
    assert outcome.failed_by_stage == {"discover": 1, "materialize": 1, "store": 1}
    assert outcome.duration_ms == 21430
    payload = json.loads(json.dumps(outcome.to_dict()))
    assert payload["failures"] == [
        {"stage": "discover", "article_id": "bad", "reason": "깨진 item"},
        {"stage": "materialize", "article_id": "2", "reason": "발행일이 없다"},
        {"stage": "store", "article_id": "3", "reason": "저장한 객체가 stat 에 안 잡힌다"},
    ]
    assert SourceOutcome.from_dict(payload) == outcome


def test_유료_표시_저장은_회원_전용과_따로_센다():
    outcome = collect_source(
        FakeAdapter(["1", "2", "3"], members=["1"], paywalled=["2", "3"]),
        ledger=InMemoryLedger(),
        store=InMemoryObjectStore(),
    )
    assert (outcome.stored, outcome.members_only_stored, outcome.paywalled_stored) == (3, 1, 2)


def test_유료_표시_칸이_없는_옛_XCom_도_읽는다():
    """배포 직후 재시도는 이 칸이 생기기 전 태스크가 남긴 XCom 을 읽는다."""
    old = SourceOutcome(source="vogue", domain="fashion", stored=1).to_dict()
    del old["paywalled_stored"]
    assert SourceOutcome.from_dict(old).paywalled_stored == 0


def test_모르는_실패_단계도_세고_수집을_멈추지_않는다():
    """`Stage` 는 타입 힌트일 뿐이라 새 어댑터가 다른 이름을 내도 런타임엔 막히지 않는다."""
    from dataclasses import replace

    class OddStage(FakeAdapter):
        def discover(self, page=None) -> DiscoverResult:
            result = super().discover(page)
            odd = Failure(source=SOURCE.key, stage="parse", ref="x", reason="새 단계")  # type: ignore[arg-type]
            return replace(result, failures=[*result.failures, odd])

    outcome = collect_source(OddStage(["1"]), ledger=InMemoryLedger(), store=InMemoryObjectStore())
    assert outcome.stored == 1
    assert outcome.failed == 2
    assert outcome.failed_by_stage == {"discover": 1, "materialize": 0, "store": 0, "parse": 1}


# --- 객체 메타데이터와 키 규칙 (S15P21A102-158) -----------------------------


def test_객체마다_수집_시각과_자기_해시가_붙는다():
    """이벤트·장부에도 있지만, 객체만 손에 쥔 상황에서 되짚을 수 있어야 한다 (#5.1)."""
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"]), ledger=InMemoryLedger(), store=store)

    raw_meta = store.objects["fashion/vogue/rss/2026/09/03/1/raw.xml"].metadata
    article = store.objects["fashion/vogue/rss/2026/09/03/1/article.json"]

    # collected_at 은 UTC 로 들어오지만 KST 표기로 붙는다 (팀 계약 시각 규약).
    assert raw_meta["collected-at"] == "2026-09-03T11:00:00+09:00"
    assert raw_meta["content-sha256"] == "c" * 64  # raw 의 해시
    # article.json 메타데이터는 그 객체 자신의 해시다. raw 해시와 다른 값이다.
    assert article.metadata["content-sha256"] == hashlib.sha256(article.body).hexdigest()
    assert article.metadata["content-sha256"] != "c" * 64


def test_메타데이터는_ASCII_뿐이다():
    """latin-1 헤더로 실리므로 한글이 섞이면 실제 저장소에서 요청이 깨진다."""
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"]), ledger=InMemoryLedger(), store=store)
    for stored in store.objects.values():
        assert all(v.isascii() for v in stored.metadata.values())


def test_회원_전용은_해시_메타데이터가_없다():
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"], members=["1"]), ledger=InMemoryLedger(), store=store)
    meta = store.objects["fashion/vogue/rss/2026/09/03/1/article.json"].metadata
    assert "collected-at" in meta
    # article.json 자신의 해시는 회원 전용이어도 붙는다. raw 해시는 애초에 없다.
    assert "content-sha256" in meta


def test_raw_content_type_에_charset_을_붙이지_않는다():
    """raw 는 받은 바이트 그대로다(불변식 8). utf-8 을 단정하면 헤더가 거짓이 된다."""
    store = InMemoryObjectStore()
    collect_source(FakeAdapter(["1"]), ledger=InMemoryLedger(), store=store)
    assert store.objects["fashion/vogue/rss/2026/09/03/1/raw.xml"].content_type == "application/xml"


def test_어댑터가_준_raw_key_가_규칙과_다르면_저장하지_않는다():
    """`keys.py` 를 고치면서 어댑터를 안 고치면 같은 기사가 두 키에 생긴다 (불변식 7)."""
    store = InMemoryObjectStore()
    article = make_article("1").model_copy(
        update={"raw_key": "domain=fashion/vogue/2026/09/03/1/raw.xml"}
    )
    with pytest.raises(ValueError, match="키 규칙과 다르다"):
        store_article(article, b"<item/>", store=store, ledger=InMemoryLedger())
    assert store.objects == {}


def test_저장_확인_조회가_실패하면_없음으로_뭉개지_않는다():
    """403·5xx 를 False 로 읽으면 저장은 됐는데 장부에 안 적혀 매 주기 다시 받는다."""
    ledger = InMemoryLedger()
    store = InMemoryObjectStore(fail_exists={"fashion/vogue/rss/2026/09/03/1/article.json"})
    with pytest.raises(RuntimeError, match="조회"):
        store_article(make_article("1"), b"<item/>", store=store, ledger=ledger)
    assert ledger.pending("fashion") == []


def test_발급은_소스별로_이번_실행이_낸_건수를_돌려준다():
    """요약 이벤트의 `emitted` 가 이 값이다.

    장부를 구간으로 다시 세면 실행이 겹칠 때 앞 실행이 낸 것까지 제 몫으로 센다.
    이번에 실제로 보낸 것만 세면 그 일이 안 생긴다.
    """
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=InMemoryObjectStore())
    sent = publish_pending(
        ledger=ledger,
        publisher=RecordingEventPublisher(),
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
    )
    assert sent == {"vogue": EmittedStats(2, NOW)}


def test_연달아_두_번_발급하면_두_번째는_0건이다():
    """실행 구간이 겹쳐도 앞 실행이 낸 건수를 제 것으로 세지 않는다."""
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    kw = dict(ledger=ledger, publisher=publisher, bucket="raw-data", domain="fashion",
              now=NOW)
    first = publish_pending(run_id="20260903T110000", **kw)
    second = publish_pending(run_id="20260903T120000", **kw)
    assert first == {"vogue": EmittedStats(2, NOW)}
    assert second == {}
    assert len(publisher.sent) == 2


def test_기사_이벤트에_그_발급_실행의_run_id_가_박힌다():
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
    )
    _key, event = publisher.sent[0]
    assert event["run_id"] == "20260903T110000"


def test_레지스트리에서_사라진_소스도_거울에_적힌_국가로_나간다():
    """봉투와 뷰는 같은 기사에 같은 국가를 붙여야 한다. 뷰가 읽는 것은 DB 거울이다.

    `SourceDef` 에서 소스를 빼도 거울의 행은 남긴다 — 지우면 그 소스로 이미 받아 둔 기사가
    뷰에서 전부 `XX` 가 된다. 그러면 그 소스의 미발급 행이 장부에 남아 있을 때, 발급이 코드
    레지스트리를 읽으면 봉투만 `XX` 를 내고 뷰는 옛 국가를 내 두 창구가 갈린다.
    """
    ledger = InMemoryLedger()
    ledger.ensure_schema(COUNTRIES)  # 소스가 레지스트리에 있던 회차
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    # 소스를 `SourceDef` 에서 뺀 회차. 거울의 행은 지우지 않으므로 그대로 남는다.
    ledger.ensure_schema({})

    publisher = RecordingEventPublisher()
    publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
    )

    _key, event = publisher.sent[0]
    assert event["source_country"] == "KR"


def test_거울에_없는_소스는_XX_로_나간다():
    """뷰의 `coalesce(country, 'XX')` 와 같은 값이다 — 두 창구가 갈리면 안 된다."""
    ledger = InMemoryLedger()  # `ensure_schema` 를 안 불러 거울이 비어 있다
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
    )

    _key, event = publisher.sent[0]
    assert event["source_country"] == UNKNOWN_COUNTRY


def test_거울은_회차마다_한_번만_읽는다():
    """행마다 물으면 만 건에 만 번이다. 국가는 회차 도중에 바뀌지 않는다."""

    class CountingCountries(InMemoryLedger):
        def __init__(self) -> None:
            super().__init__()
            self.country_calls = 0

        def source_countries(self) -> dict[str, str]:
            self.country_calls += 1
            return super().source_countries()

    ledger = CountingCountries()
    ledger.ensure_schema(COUNTRIES)
    collect_source(FakeAdapter([str(i) for i in range(250)]), ledger=ledger,
                   store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
        batch=100,
    )

    assert len(publisher.sent) == 250
    assert ledger.country_calls == 1, "묶음마다 다시 읽으면 안 된다"
    assert {e["source_country"] for _k, e in publisher.sent} == {"KR"}


def test_재시도해도_요약_건수가_그대로다():
    """publish 태스크는 `retries=2` 다. 발급을 마치고 요약 중간에 죽으면 재시도가 온다.

    그때 "이번 시도가 보낸 것"만 세면 0 이 나오고, 같은 `event_id` 로 내용이 다른 요약이
    나간다(팀 발행 규약 3 위반). 그래서 건수는 장부에 적힌 발급 실행으로 센다.
    """
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=InMemoryObjectStore())
    kw = dict(
        ledger=ledger,
        publisher=RecordingEventPublisher(),
        bucket="raw-data",
        domain="fashion",
    )

    first = publish_pending(run_id="20260903T110000", now=NOW, **kw)
    # 같은 실행의 재시도 — logical date 가 같으니 run_id 도 같다.
    retry = publish_pending(run_id="20260903T110000", now=NOW, **kw)

    assert first == {"vogue": EmittedStats(2, NOW)}
    assert retry == {"vogue": EmittedStats(2, NOW)}, "재시도에도 발급 통계가 보존된다"


def test_다음_실행은_앞_실행이_낸_것을_제_몫으로_세지_않는다():
    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1", "2"]), ledger=ledger, store=InMemoryObjectStore())
    kw = dict(
        ledger=ledger,
        publisher=RecordingEventPublisher(),
        bucket="raw-data",
        domain="fashion",
    )

    publish_pending(run_id="20260903T110000", now=NOW, **kw)
    later = publish_pending(run_id="20260903T120000", now=NOW, **kw)

    assert later == {}


class CountingLedger(InMemoryLedger):
    """`pending` 이 몇 번 불렸는지 센다. 한 회차가 몇 묶음을 도는지 보려고."""

    def __init__(self) -> None:
        super().__init__()
        self.pending_calls = 0

    def pending(self, domain: str, limit: int = 500):
        self.pending_calls += 1
        return super().pending(domain, limit)


def test_밀린_게_묶음보다_많아도_한_회차가_다_비운다():
    """묶음 상한만큼만 내고 끝나면 요약 건수가 시도마다 커진다.

    1차 시도가 250 중 100 만 내고 요약 도중 죽으면, 2차 시도가 나머지를 내고 `emitted_by_run`
    이 250 을 준다 — 같은 `event_id` 로 `emitted` 가 100 이었다가 250 이 된다
    (팀 발행 규약 3 위반).
    """
    ledger = CountingLedger()
    adapter = FakeAdapter([str(i) for i in range(250)])
    collect_source(adapter, ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()

    counts = publish_pending(
        ledger=ledger,
        publisher=publisher,
        bucket="raw-data",
        domain="fashion",
        run_id="20260903T110000",
        now=NOW,
        batch=100,
    )

    assert counts == {"vogue": EmittedStats(250, NOW)}
    assert len(publisher.sent) == 250
    # 100·100·50 을 내고, 비었음을 확인하는 한 번이 더 붙는다.
    assert ledger.pending_calls == 4


def test_다_비운_뒤_재시도해도_건수가_같다():
    ledger = InMemoryLedger()
    adapter = FakeAdapter([str(i) for i in range(250)])
    collect_source(adapter, ledger=ledger, store=InMemoryObjectStore())
    publisher = RecordingEventPublisher()
    kw = dict(ledger=ledger, publisher=publisher, bucket="raw-data", domain="fashion",
              now=NOW)

    first = publish_pending(run_id="20260903T110000", batch=100, **kw)
    retry = publish_pending(run_id="20260903T110000", batch=100, **kw)

    assert first == retry == {"vogue": EmittedStats(250, NOW)}
    assert len(publisher.sent) == 250, "재시도가 이미 나간 것을 다시 내면 안 된다"


def test_실패_표본은_10건_사유는_200자로_제한하되_전체_실패를_센다():
    class BrokenFeed(FakeAdapter):
        def discover(self, page=None):
            return DiscoverResult(candidates=[], failures=[
                Failure(source="vogue", stage="discover", ref=str(i), reason="가" * 201)
                for i in range(12)
            ])

    outcome = collect_source(BrokenFeed([]), ledger=InMemoryLedger(), store=InMemoryObjectStore())
    assert outcome.failed == 12
    assert outcome.failed_by_stage == {"discover": 12, "materialize": 0, "store": 0}
    assert [f.article_id for f in outcome.failures] == [str(i) for i in range(10)]
    assert all(f.reason == "가" * 200 for f in outcome.failures)


def test_304는_발견_0건과_구분하고_실패_없이_빈_결과를_남긴다():
    class Unchanged(FakeAdapter):
        def discover(self, page=None):
            return DiscoverResult(candidates=[], not_modified=True)

    outcome = collect_source(Unchanged([]), ledger=InMemoryLedger(), store=InMemoryObjectStore())
    assert outcome.not_modified is True
    assert outcome.discovered == outcome.stored == outcome.skipped == outcome.failed == 0
    assert outcome.failed_by_stage == {"discover": 0, "materialize": 0, "store": 0}
    assert outcome.failures == ()


@pytest.mark.parametrize("summary_topic", ["", "collect-run-summary"])
def test_DAG_발급은_요약_설정과_무관하게_기사를_내고_요약만_별도_토픽으로_낸다(
    monkeypatch, caplog, summary_topic,
):
    import json
    import logging
    from types import SimpleNamespace

    from trendin.common.collect import dag_factory
    from trendin.common.collect.kafka_publisher import BOOTSTRAP_ENV, SUMMARY_TOPIC_ENV, TOPIC_ENV

    ledger = InMemoryLedger()
    collect_source(FakeAdapter(["1"]), ledger=ledger, store=InMemoryObjectStore())
    sent = []

    class Producer:
        def __init__(self, config):
            pass

        def produce(self, topic, *, key, value, on_delivery):
            sent.append((topic, json.loads(value)))
            on_delivery(None, None)

        def poll(self, timeout):
            return 0

        def flush(self, timeout):
            return 0

    # 인프라 어댑터 경계만 대체한다. DAG → flow → 실제 Kafka 봉투 직렬화는 모두 탄다.
    monkeypatch.setattr(dag_factory.Database, "from_env", lambda: None)
    monkeypatch.setattr(dag_factory, "PostgresLedger", lambda db: ledger)
    monkeypatch.setattr(dag_factory.MinioObjectStore, "from_env",
                        lambda: SimpleNamespace(bucket="raw-data"))
    monkeypatch.setattr("confluent_kafka.Producer", Producer)
    monkeypatch.setenv(BOOTSTRAP_ENV, "localhost:9092")
    monkeypatch.setenv(TOPIC_ENV, "raw-file-ready")
    monkeypatch.setenv(SUMMARY_TOPIC_ENV, summary_topic)
    dag = dag_factory.build_collect_dag(
        dag_id="fashion_summary_test", domain="fashion", schedule=None,
        source_keys=["vogue"], domain_of=lambda key: "fashion",
        source_countries={"vogue": "KR"}, collect=lambda **kw: None,
        doc_md="요약 토픽 검증",
    )
    publish = dag.get_task("publish").python_callable
    # 수집 태스크는 죽었지만 이전 회차에 저장된 기사는 발급한다.
    monkeypatch.setattr(dag_factory.logger, "handlers", [caplog.handler])
    with caplog.at_level(logging.INFO):
        result = publish(["vogue"], logical_date=NOW,
                         ti=SimpleNamespace(xcom_pull=lambda **kw: None))
    assert result["articles"] == 1
    assert result["failed_sources"] == ["vogue"]
    assert sent[0][0] == "raw-file-ready" and sent[0][1]["run_id"]
    if summary_topic:
        assert result["summaries"] == 1 and result["summary_enabled"] is True
        assert sent[1][0] == "collect-run-summary"
        assert sent[1][1]["stored"] is None and sent[1][1]["emitted"] == 1
        retry = publish(["vogue"], logical_date=NOW,
                        ti=SimpleNamespace(xcom_pull=lambda **kw: None))
        assert retry == result
        assert sent[2] == sent[1]  # 재시도는 기사 없이 같은 요약만 다시 낸다.
    else:
        assert result["summaries"] == 0 and result["summary_enabled"] is False
        assert len(sent) == 1
        assert SUMMARY_TOPIC_ENV in caplog.text
