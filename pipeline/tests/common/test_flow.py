"""수집 실행 흐름 (설계 문서 #4, S15P21A102-167).

여기서 지키는 것: 장부가 발견과 취득 사이에서 거른다, 저장이 확인된 뒤에만 장부에 적는다,
기사 하나가 깨져도 나머지는 간다, 재시도하면 안 되는 실패는 올라간다, 페이지를 못 받은
기사는 상한까지만 다시 시도한다.

**발급 테스트는 없다.** 브로커를 걷으면서(Kafka 제거 3/3) 저장 다음 단계가 없어졌다 —
장부에 적힌 행은 `collected_article_event` 뷰에 바로 나타난다. 그 뷰가 맞는지는 진짜
PostgreSQL 이 있어야 볼 수 있어서 `tests/common/test_ledger_view.py` 에 있다.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import (
    ArticleFetchError,
    Candidate,
    DiscoverResult,
    Failure,
    FetchMeta,
    SourceDef,
)
from trendin.common.collect.doubles import InMemoryObjectStore
from trendin.common.collect.flow import (
    RETRY_LIMIT,
    RETRY_WINDOW,
    SourceOutcome,
    abandoned_article,
    collect_source,
    store_article,
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
            else raw_key(SOURCE.domain, SOURCE.key, SOURCE.route, published, article_id, ext="xml")
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
    assert ledger.rows("fashion") == []
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
    assert len(ledger.rows("fashion")) == 2


# --- DAG 이 들고 있던 판정 ---------------------------------------------------
# 규약 1 대로 DAG 파일에서 내려온 것들. 내려왔으니 Airflow 없이 테스트된다(규약 12).


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
    assert ledger.rows("fashion") == []


def test_실패_표본은_10건_사유는_200자로_제한하되_전체_실패를_센다():
    class BrokenFeed(FakeAdapter):
        def discover(self, page=None):
            return DiscoverResult(
                candidates=[],
                failures=[
                    Failure(source="vogue", stage="discover", ref=str(i), reason="가" * 201)
                    for i in range(12)
                ],
            )

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


# --- 대기·재시도 (S15P21A102-312) -------------------------------------------


def meta_for(article_id: str) -> FetchMeta:
    return FetchMeta(
        domain=SOURCE.domain,
        source=SOURCE.key,
        route=SOURCE.route,
        article_id=article_id,
        url=f"https://www.vogue.co.kr/{article_id}/",
        title=f"제목 {article_id}",
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        categories=("fashion",),
    )


class FetchFailingAdapter:
    """기사 페이지를 못 받는 대역. `ok` 에 든 id 는 그때부터 성공한다."""

    source = SOURCE

    def __init__(self, ids, *, ok=(), retryable=True, blocking=False):
        self._ids = list(ids)
        self._ok = set(ok)
        self._retryable = retryable
        self._blocking = blocking
        self.materialized: list[str] = []

    def discover(self, page=None) -> DiscoverResult:
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
            ]
        )

    def materialize(self, candidate: Candidate):
        self.materialized.append(candidate.article_id)
        if candidate.article_id in self._ok:
            return b"<html/>", make_article(candidate.article_id)
        raise ArticleFetchError(
            "타임아웃",
            meta=meta_for(candidate.article_id),
            retryable=self._retryable,
            blocking=self._blocking,
        )


def test_페이지를_못_받으면_저장하지_않고_대기로_남는다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    outcome = collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store)

    assert outcome.stored == 0 and outcome.failed == 1
    assert store.objects == {}  # MinIO 에 아무것도 쓰지 않는다
    assert ledger.rows("fashion") == []  # 발급도 되지 않는다
    (row,) = ledger.retrying(SOURCE.key)
    assert row.attempts == 1 and row.meta.title == "제목 1"


def test_대기_행은_다음_주기에_다시_후보가_된다():
    """불변식 12 에 둔 예외다 — 장부에 있어도 아직 안 받은 기사다."""
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store)

    again = FetchFailingAdapter(["1"], ok=["1"])
    outcome = collect_source(again, ledger=ledger, store=store)

    assert again.materialized == ["1"]
    assert outcome.stored == 1
    assert ledger.retrying(SOURCE.key) == []  # 성공했으니 대기가 아니다
    assert len(ledger.rows("fashion")) == 1  # 행이 늘지 않았다 (불변식 7)


def test_시도_상한에_닿으면_본문_없이_저장한다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    for _ in range(RETRY_LIMIT):
        outcome = collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store)

    assert outcome.stored == 1
    assert list(store.objects) == ["fashion/vogue/rss/2026/09/03/1/article.json"]
    (row,) = ledger.rows("fashion")
    assert row.raw_key is None and row.title == "제목 1"
    assert ledger.retrying(SOURCE.key) == []


def test_24시간이_지나면_시도가_남아도_포기한다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store, now=lambda: NOW)
    later = NOW + RETRY_WINDOW
    collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store, now=lambda: later)

    assert list(store.objects) == ["fashion/vogue/rss/2026/09/03/1/article.json"]
    assert ledger.retrying(SOURCE.key) == []


def test_404_는_첫_실패에_포기한다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    outcome = collect_source(
        FetchFailingAdapter(["1"], retryable=False), ledger=ledger, store=store
    )
    assert outcome.stored == 1
    assert ledger.retrying(SOURCE.key) == []


def test_403_은_대기를_남기고_그_실행을_멈춘다():
    """불변식 2 — 그 실행에서 이 호스트는 끝이다. 다음 주기에는 다시 시도한다."""
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    with pytest.raises(ArticleFetchError):
        collect_source(FetchFailingAdapter(["1", "2"], blocking=True), ledger=ledger, store=store)

    (row,) = ledger.retrying(SOURCE.key)
    assert row.meta.article_id == "1"  # 둘째 기사는 치지도 않았다


def test_피드에서_사라진_대기_행도_상한에_닿으면_포기한다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    collect_source(FetchFailingAdapter(["1"]), ledger=ledger, store=store, now=lambda: NOW)

    later = NOW + RETRY_WINDOW
    # 기사가 피드에서 밀려나 후보에 없다.
    outcome = collect_source(FetchFailingAdapter([]), ledger=ledger, store=store, now=lambda: later)

    assert outcome.stored == 1
    assert ledger.retrying(SOURCE.key) == []
    (row,) = ledger.rows("fashion")
    assert row.raw_key is None


def test_대기_행을_새_후보보다_먼저_처리한다():
    ledger, store = InMemoryLedger(), InMemoryObjectStore()
    collect_source(FetchFailingAdapter(["2"]), ledger=ledger, store=store)

    again = FetchFailingAdapter(["1", "2"], ok=["1", "2"])
    collect_source(again, ledger=ledger, store=store)

    assert again.materialized == ["2", "1"]


def test_포기한_기사는_본문도_raw_도_없다():
    article = abandoned_article(meta_for("7"), NOW)
    assert article.fetch_failed is True
    assert article.body_text is None and article.raw_key is None
    assert article.categories == ["fashion"]
    assert article.to_json_dict()["fetch_failed"] is True
