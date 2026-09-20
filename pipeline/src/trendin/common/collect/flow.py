"""수집 실행 흐름 (설계 문서 #4, S15P21A102-167).

순서는 발견 → 장부로 거름 → 취득·정규화 → 저장 → 있음 확인 → 장부 기록이다. **장부에
적기 전에 저장을 확인한다**(불변식 5) — 소비 측이 보는 것은 장부이고, 그 행이 가리키는
객체가 없으면 안 된다.

**발급은 이제 없다.** 브로커를 걷으면서(Kafka 제거 3/3) 저장과 소비 사이의 단계가 하나
줄었다 — 장부에 적힌 행은 `collected_article_event` 뷰에 그 순간 나타나고, 소비 측이
그것을 읽는다. 그래서 "저장은 됐는데 아직 안 나간 행" 이라는 중간 상태가 사라졌고,
그 상태를 이어 내던 `publish_pending` 도 함께 없어졌다.

이 모듈은 airflow 를 import 하지 않는다(README 규약 12). DAG 파일은 실행 순서와 Airflow
설정만 들고, 판정은 전부 여기 있다 — `run_id` 만들기, 재시도해도 되는 실패와 그러면 안 되는
실패 가르기까지.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, get_args

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import (
    ArticleFetchError,
    Candidate,
    Failure,
    FetchMeta,
    SourceAdapter,
    Stage,
)
from trendin.common.collect.keys import article_key, raw_ext, raw_key
from trendin.common.collect.ledger import Ledger, RetryRow
from trendin.common.collect.session import (
    BlockedUserAgent,
    HostBlocked,
    UrlNotAllowed,
)
from trendin.common.collect.sinks import ARTICLE_CONTENT_TYPE, CONTENT_TYPES, ObjectStore

logger = logging.getLogger("trendin.collect.flow")

KST = timezone(timedelta(hours=9), "KST")

# 다시 시도하면 불변식을 깨는 실패들. 403·429 는 "그 실행에서 그 호스트를 멈추고 IP·UA 를
# 바꿔 재시도하지 않는다"(불변식 2)이고, 허용 범위 밖·차단 UA 는 애초에 보내면 안 되는
# 요청(`source-discovery.md` 불변식 18, 불변식 2)이라 5분 뒤에 다시 보내도 똑같이 안 된다.
# 여기 없는 실패(`FetchFailed` — 타임아웃·5xx)는 재시도가 의미 있다.
NO_RETRY = (BlockedUserAgent, UrlNotAllowed, HostBlocked)

# 기사 페이지를 못 받은 기사를 다시 시도하는 상한 (S15P21A102-312). 둘 중 하나에 닿으면
# 포기하고 본문 없이 저장한다. 불변식 12 의 "장부에 있는 기사는 다시 받지 않는다" 에 둔
# 예외라 상한이 필요하다 — 없으면 못 받는 기사 한 건이 매 회차 요청을 되풀이한다.
RETRY_LIMIT = 3
RETRY_WINDOW = timedelta(hours=24)

FAILURE_SAMPLE_LIMIT = 10
FAILURE_REASON_MAX = 200


@dataclass(frozen=True, slots=True)
class FailureBrief:
    """요약에 싣는 실패 표본. 사유는 200자까지만 보존한다."""

    stage: Stage
    article_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    """소스 하나가 이번 실행에서 한 일. 요약 이벤트(#6)의 재료다."""

    source: str
    domain: str
    discovered: int = 0
    stored: int = 0
    skipped: int = 0  # 장부에 이미 있어 받지 않은 후보 (불변식 12)
    not_modified: bool = False  # 조건부 요청이 304 — "새 글 0건"과 다르다
    failed: int = 0
    failed_by_stage: dict[str, int] = field(
        default_factory=lambda: {"discover": 0, "materialize": 0, "store": 0}
    )
    failures: tuple[FailureBrief, ...] = ()
    duration_ms: int = 0
    members_only_stored: int = 0
    paywalled_stored: int = 0

    def to_dict(self) -> dict:
        """XCom 으로 넘길 수 있는 모양.

        예외 문자열은 길이를 예측할 수 없어 원래 제외했다. 표본 10건·사유 200자로
        상한을 두어 실패 이유도 전달한다. 본문은 여전히 싣지 않는다(규약 4).
        """
        data = asdict(self)
        data["failures"] = [asdict(failure) for failure in self.failures]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SourceOutcome":
        values = data.copy()
        values["failures"] = tuple(FailureBrief(**failure) for failure in data.get("failures", []))
        return cls(**values)


def article_bytes(article: Article) -> bytes:
    """MinIO 에 쓸 article.json 바이트. 같은 기사는 같은 바이트여야 한다(불변식 7)."""
    return article.model_dump_json(exclude_none=True).encode("utf-8")


def _give_up_now(row: RetryRow, now: datetime) -> bool:
    """더 시도하지 않는다. 횟수를 다 썼거나 창을 넘겼다."""
    return row.attempts >= RETRY_LIMIT or now - row.first_failed_at >= RETRY_WINDOW


def abandoned_article(meta: FetchMeta, collected_at: datetime) -> Article:
    """페이지를 끝내 못 받은 기사. 제목·URL·발행일·분류만 있고 본문도 raw 도 없다."""
    return Article(
        domain=meta.domain,
        source=meta.source,
        route=meta.route,
        article_id=meta.article_id,
        url=meta.url,
        title=meta.title,
        published_at=meta.published_at,
        collected_at=collected_at,
        categories=list(meta.categories),
        fetch_failed=True,
    )


def store_candidates(
    adapter: SourceAdapter,
    candidates: Iterable[Candidate],
    *,
    ledger: Ledger,
    store: ObjectStore,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[int, int, int, list[Failure]]:
    """후보를 취득·정규화해 저장하고 장부에 적는다.

    저장 건수·회원 전용 저장 건수·유료 표시 저장 건수·실패 목록을 돌려준다.

    주기 실행과 백필이 같은 루프를 쓴다. 백필이 제 루프를 따로 두면 저장 확인·장부 기록
    순서가 두 벌로 갈리고, 한쪽만 고쳐지는 날이 온다.
    """
    source = adapter.source
    stored = 0
    members_only_stored = 0
    paywalled_stored = 0
    failures: list[Failure] = []

    for candidate in candidates:
        try:
            raw, article = adapter.materialize(candidate)
        except ArticleFetchError as exc:
            # 기사 페이지를 못 받았다. 장부에 대기 행으로 남겨 다음 주기에 다시 시도한다
            # (S15P21A102-312). MinIO 에는 아무것도 쓰지 않는다.
            logger.warning("%s: 페이지를 못 받았다 %s — %s", source.key, candidate.article_id, exc)
            failures.append(Failure(source.key, "materialize", candidate.article_id, exc.reason))
            if exc.meta is not None:
                moment = now()
                row = ledger.mark_retry(exc.meta, at=moment)
                if not exc.retryable or _give_up_now(row, moment):
                    article = abandoned_article(exc.meta, moment)
                    if store_article(article, b"", store=store, ledger=ledger):
                        stored += 1
                        logger.info(
                            "%s: 포기하고 본문 없이 저장 %s", source.key, article.article_id
                        )
            if exc.blocking:
                raise  # 그 실행에서 이 호스트는 끝이다 (불변식 2)
            continue
        except NO_RETRY:
            raise
        except Exception as exc:  # 기사 하나가 깨져도 나머지는 간다
            logger.warning("%s: 취득 실패 %s — %s", source.key, candidate.article_id, exc)
            failures.append(
                Failure(
                    source=source.key,
                    stage="materialize",
                    ref=candidate.article_id,
                    reason=str(exc),
                )
            )
            continue

        if store_article(article, raw, store=store, ledger=ledger):
            stored += 1
            members_only_stored += int(bool(article.members_only))
            paywalled_stored += int(bool(article.paywalled))
        else:
            logger.warning("%s: 저장 확인 실패 %s", source.key, article.article_id)
            failures.append(
                Failure(
                    source=source.key,
                    stage="store",
                    ref=article.article_id,
                    reason="저장한 객체가 stat 에 안 잡힌다",
                )
            )
    return stored, members_only_stored, paywalled_stored, failures


def collect_source(
    adapter: SourceAdapter,
    *,
    ledger: Ledger,
    store: ObjectStore,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> SourceOutcome:
    """소스 하나를 돈다. 기사 한 건의 실패는 나머지를 멈추지 않는다(불변식 9 의 실패 단위).

    발견 자체가 실패하면 예외가 그대로 올라간다 — 그 소스는 이번 실행에서 할 일이 없고,
    재시도할지 말지는 예외 종류가 정한다(`NO_RETRY`).
    """
    started = time.monotonic()
    source = adapter.source
    result = adapter.discover()

    new_ids = ledger.filter_new(source.key, [c.article_id for c in result.candidates])
    fresh = [c for c in result.candidates if c.article_id in new_ids]

    # 그 소스의 대기 행을 먼저 처리한다 — 오래 기다린 것이 먼저 나간다 (S15P21A102-312).
    waiting = [row.meta.article_id for row in ledger.retrying(source.key)]
    order = {article_id: position for position, article_id in enumerate(waiting)}
    fresh.sort(key=lambda c: order.get(c.article_id, len(order)))

    stored, members_only_stored, paywalled_stored, failures = store_candidates(
        adapter, fresh, ledger=ledger, store=store, now=now
    )
    stored += abandon_expired(source.key, ledger=ledger, store=store, now=now)
    for failure in result.failures:
        logger.warning("%s: 발견 실패 %s — %s", source.key, failure.ref, failure.reason)

    all_failures = [*result.failures, *failures]
    # 세 단계는 0 이어도 싣는다. 모르는 단계는 키를 늘려 센다 — 저장을 마친 뒤라 여기서
    # 죽으면 태스크만 실패하고 수집 결과(XCom)가 날아간다.
    failed_by_stage: dict[str, int] = dict.fromkeys(get_args(Stage), 0)
    for failure in all_failures:
        failed_by_stage[failure.stage] = failed_by_stage.get(failure.stage, 0) + 1

    return SourceOutcome(
        source=source.key,
        domain=source.domain,
        discovered=len(result.candidates),
        stored=stored,
        skipped=len(result.candidates) - len(fresh),
        not_modified=result.not_modified,
        failed=len(all_failures),
        failed_by_stage=failed_by_stage,
        failures=tuple(
            FailureBrief(f.stage, f.ref, f.reason[:FAILURE_REASON_MAX])
            for f in all_failures[:FAILURE_SAMPLE_LIMIT]
        ),
        duration_ms=int((time.monotonic() - started) * 1000),
        members_only_stored=members_only_stored,
        paywalled_stored=paywalled_stored,
    )


def abandon_expired(
    source_key: str,
    *,
    ledger: Ledger,
    store: ObjectStore,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> int:
    """이번 회차 후보에 없었던 대기 행 중 상한을 넘긴 것을 포기시킨다 (S15P21A102-312).

    후보에 들어 있던 대기 행은 `store_candidates` 가 이미 다뤘다. 여기 남는 것은 기사가
    피드에서 밀려나 다시 시도할 길이 없어진 행이다 — 기다려도 결과가 달라지지 않는다.
    """
    moment = now()
    abandoned = 0
    for row in ledger.retrying(source_key):
        if not _give_up_now(row, moment):
            continue
        article = abandoned_article(row.meta, moment)
        if store_article(article, b"", store=store, ledger=ledger):
            abandoned += 1
            logger.info("%s: 피드에서 사라져 포기 %s", source_key, article.article_id)
    return abandoned


def object_metadata(collected_at: datetime, sha256: str | None) -> dict[str, str]:
    """객체에 붙는 메타데이터 (설계 문서 #5.1).

    이벤트와 장부에도 같은 값이 있지만, 객체만 손에 쥔 상황에서 "언제 받은 것이고 내용이
    무엇이었나"를 되짚을 수 있어야 해서 여기에도 둔다. `content-sha256` 은 그 객체 자신의
    해시다 — raw 객체에는 raw 의 해시, article.json 에는 article.json 의 해시.
    """
    meta = {"collected-at": collected_at.astimezone(KST).isoformat()}
    if sha256:
        meta["content-sha256"] = sha256
    return meta


def store_article(article: Article, raw: bytes, *, store: ObjectStore, ledger: Ledger) -> bool:
    """raw 와 article.json 을 쓰고, 둘 다 있는 것을 확인한 뒤 장부에 적는다.

    회원 전용 기사는 raw 를 쓰지 않는다 — `Article` 이 `raw_key` 를 비워 오는 것이 그
    계약이다(불변식 2). 그래서 확인 대상도 article.json 하나뿐이다.
    """
    key = article_key(
        article.domain,
        article.source,
        article.route,
        article.published_at,
        article.article_id,
    )
    body = article_bytes(article)
    body_sha256 = hashlib.sha256(body).hexdigest()

    if article.raw_key:
        # 어댑터가 계산한 키를 규칙으로 다시 만들어 맞춰 본다. `keys.py` 를 고치면서
        # 어댑터를 안 고치면 여기서 드러난다 — 안 보면 같은 기사가 두 키에 생긴다(불변식 7).
        # 확장자는 내용이 정하므로 규칙이 알 수 없다. 키에 적힌 것을 믿고 나머지를 대조한다.
        ext = raw_ext(article.raw_key)
        expected = raw_key(
            article.domain,
            article.source,
            article.route,
            article.published_at,
            article.article_id,
            ext=ext,
        )
        if expected != article.raw_key:
            raise ValueError(
                f"raw_key 가 키 규칙과 다르다: article={article.raw_key!r} 규칙={expected!r}"
            )
        store.put(
            article.raw_key,
            raw,
            CONTENT_TYPES[ext],
            object_metadata(article.collected_at, article.content_sha256),
        )
    store.put(
        key,
        body,
        ARTICLE_CONTENT_TYPE,
        object_metadata(article.collected_at, body_sha256),
    )

    # 불변식 5 — 소비자가 키로 읽었을 때 반드시 있어야 한다.
    if not store.exists(key):
        return False
    if article.raw_key and not store.exists(article.raw_key):
        return False

    ledger.record(article, article_key=key, article_sha256=body_sha256)
    return True
