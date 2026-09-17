"""수집 실행 흐름 (설계 문서 #4, S15P21A102-167).

순서는 발견 → 장부로 거름 → 취득·정규화 → 저장 → 있음 확인 → 장부 기록, 그리고 따로
발급이다. **저장 확인 전에 발급하지 않는다**(불변식 5).

발급을 같은 함수에 두지 않은 이유는 재시도 복구다. 저장까지 하고 발급 전에 죽은 행은
`event_emitted_at` 이 비어 있고, 다음 실행의 발급이 장부를 훑어 그걸 이어 낸다(#4).
그래서 발급은 "이번에 저장한 것"이 아니라 "아직 안 나간 것 전부"를 본다.

이 모듈은 airflow 를 import 하지 않는다(README 규약 12). DAG 파일은 실행 순서와 Airflow
설정만 들고, 판정은 전부 여기 있다 — `run_id` 만들기, 죽은 소스 골라내기, 재시도해도 되는
실패와 그러면 안 되는 실패 가르기까지.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Sequence, get_args

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import (
    UNKNOWN_COUNTRY,
    Candidate,
    Failure,
    SourceAdapter,
    Stage,
)
from trendin.common.collect.events import article_event, run_summary_event
from trendin.common.collect.keys import article_key, raw_ext, raw_key
from trendin.common.collect.ledger import EmittedStats, Ledger
from trendin.common.collect.session import (
    BlockedUserAgent,
    HostBlocked,
    UrlNotAllowed,
)
from trendin.common.collect.sinks import (
    ARTICLE_CONTENT_TYPE,
    CONTENT_TYPES,
    EventPublisher,
    ObjectStore,
)

logger = logging.getLogger("trendin.collect.flow")

KST = timezone(timedelta(hours=9), "KST")

# 다시 시도하면 불변식을 깨는 실패들. 403·429 는 "그 실행에서 그 호스트를 멈추고 IP·UA 를
# 바꿔 재시도하지 않는다"(불변식 2)이고, 허용 범위 밖·차단 UA 는 애초에 보내면 안 되는
# 요청(`source-discovery.md` 불변식 18, 불변식 2)이라 5분 뒤에 다시 보내도 똑같이 안 된다.
# 여기 없는 실패(`FetchFailed` — 타임아웃·5xx)는 재시도가 의미 있다.
NO_RETRY = (BlockedUserAgent, UrlNotAllowed, HostBlocked)

TASK_FAILED_REASON = "태스크가 실패했다 (로그 참조)"


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


@dataclass(frozen=True, slots=True)
class SourceStatus:
    """소스 하나의 이번 실행 성패. 요약 이벤트 하나가 여기서 나온다."""

    source: str
    domain: str
    status: str  # "success" | "failed"
    failure_reason: str | None = None
    outcome: SourceOutcome | None = None


def run_id_of(logical_date: datetime) -> str:
    """팀 계약의 `run_id` — logical date 파생 `yyyyMMddTHHmmss` (KST). 재시도해도 같다."""
    return logical_date.astimezone(KST).strftime("%Y%m%dT%H%M%S")


def source_statuses(
    source_keys: Sequence[str],
    outcomes: Iterable[SourceOutcome],
    domain_of: Callable[[str], str],
) -> list[SourceStatus]:
    """결과를 남긴 소스는 성공, 목록에 있는데 안 돌아온 소스는 실패다.

    수집 태스크가 재시도까지 소진해 죽으면 그 인스턴스는 XCom 을 남기지 않는다. 그래서
    "소스 목록 빼기 돌아온 소스" 가 곧 죽은 소스다 — 팀 발행 규약 5 가 요구하는
    `status: failed` 를 그 차집합으로 만든다.
    """
    alive = {o.source: o for o in outcomes}
    statuses = []
    for key in source_keys:
        outcome = alive.get(key)
        if outcome is None:
            statuses.append(
                SourceStatus(
                    source=key,
                    domain=domain_of(key),
                    status="failed",
                    failure_reason=TASK_FAILED_REASON,
                )
            )
        else:
            statuses.append(
                SourceStatus(source=key, domain=outcome.domain, status="success", outcome=outcome)
            )
    return statuses


def outcomes_from_xcom(pulled) -> list[SourceOutcome]:
    """매핑 태스크의 XCom 을 결과 목록으로 되돌린다.

    매핑이 한 건이면 dict 하나로, 여러 건이면 목록으로 온다. 죽은 인스턴스는 아예 빠진다.
    """
    if pulled is None:
        return []
    if isinstance(pulled, dict):
        pulled = [pulled]
    return [SourceOutcome.from_dict(d) for d in pulled if d]


def article_bytes(article: Article) -> bytes:
    """MinIO 에 쓸 article.json 바이트. 같은 기사는 같은 바이트여야 한다(불변식 7)."""
    return article.model_dump_json(exclude_none=True).encode("utf-8")


def store_candidates(
    adapter: SourceAdapter,
    candidates: Iterable[Candidate],
    *,
    ledger: Ledger,
    store: ObjectStore,
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


def collect_source(adapter: SourceAdapter, *, ledger: Ledger, store: ObjectStore) -> SourceOutcome:
    """소스 하나를 돈다. 기사 한 건의 실패는 나머지를 멈추지 않는다(불변식 9 의 실패 단위).

    발견 자체가 실패하면 예외가 그대로 올라간다 — 그 소스는 이번 실행에서 할 일이 없고,
    재시도할지 말지는 예외 종류가 정한다(`NO_RETRY`).
    """
    started = time.monotonic()
    source = adapter.source
    result = adapter.discover()

    new_ids = ledger.filter_new(source.key, [c.article_id for c in result.candidates])
    fresh = [c for c in result.candidates if c.article_id in new_ids]

    stored, members_only_stored, paywalled_stored, failures = store_candidates(
        adapter, fresh, ledger=ledger, store=store
    )
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


def publish_pending(
    *,
    ledger: Ledger,
    publisher: EventPublisher,
    bucket: str,
    domain: str,
    run_id: str,
    now: datetime,
    batch: int = 500,
) -> dict[str, EmittedStats]:
    """그 도메인에서 아직 안 나간 행을 전부 낸다. 지난 실행의 미발급분이 여기 딸려 온다.

    순서는 발행 → 장부 기록이다. 뒤집으면 기록 뒤 발행 전에 죽었을 때 그 기사가 영영 안
    나간다. 이 순서면 중복이 날 수 있는데, 그건 소비 측이 `event_id` 로 거르기로 팀
    계약에 적혀 있다(at-least-once).

    소스별 발급 건수와 가장 오래된 수집 시각이 요약의 발급 통계다. 그 값을
    **장부에 적힌 발급 실행**으로 세는 데는 이유가 둘 있다.

    이번 시도가 보낸 것만 세면 재시도에서 뒤집힌다 — 발급까지 마치고 요약 중간에 죽으면
    다음 시도는 보낼 게 없어 0 이 되고, 같은 `event_id` 로 내용이 다른 요약이 나간다.

    실행 구간으로 세면 겹칠 때 부푼다 — 실행 둘이 가까우면 앞 실행이 낸 것까지 센다.

    **밀린 것을 다 비운다.** 묶음 상한에서 끊으면 1차 시도가 100 건, 2차 시도가 250 건을
    세어 같은 `event_id` 로 `emitted` 가 다른 요약이 나간다. 다 비우면 재시도는 낼
    것이 없어 값이 그대로다. `batch` 는 한 번에 메모리에 들 행 수지 한 회차의 상한이 아니다.

    봉투의 `source_country` 는 **장부의 국가 거울**에서 온다. 국가는 기사가 아니라 소스의
    속성이라 장부 행(`PendingArticle`)에 없고, 소비 측이 읽는 뷰도 같은 거울을 읽는다.
    """
    # 거울을 회차마다 한 번만 읽는다. 행마다 물으면 만 건에 만 번이다. 이 루프 도중에는
    # 바뀌지 않는다 — 거울을 고치는 것은 같은 DAG 의 `ensure_schema` 태스크뿐이고 그건
    # 이 태스크보다 앞에서 끝났다.
    countries = ledger.source_countries()
    while True:
        rows = ledger.pending(domain, batch)
        if not rows:
            break
        for row in rows:
            # message key 는 `source_id` 다(팀 계약). 같은 소스의 이벤트가 한 파티션에 모여
            # 순서가 보장된다. 요약은 별도 토픽이라 두 토픽 사이 순서는 보장하지 않는다.
            publisher.publish(
                row.source,
                article_event(
                    row,
                    bucket=bucket,
                    run_id=run_id,
                    # 거울에 없는 소스는 `UNKNOWN_COUNTRY`. 장부 뷰의
                    # `coalesce(country, 'XX')` 와 같은 값을 내야 한다 — 두 창구가 같은
                    # 기사에 다른 국가를 붙이면 안 된다.
                    source_country=countries.get(row.source, UNKNOWN_COUNTRY),
                ),
            )
        publisher.flush()
        # 한 묶음을 한 트랜잭션으로 적는다. 행마다 열면 만 건에 만 번이고, 중간에 죽으면
        # 절반만 적힌 채로 남는다.
        ledger.mark_emitted_many([(r.source, r.article_id) for r in rows], now, run_id)
    return ledger.emitted_by_run(domain, run_id)


def publish_summaries(
    *,
    publisher: EventPublisher,
    run_id: str,
    logical_date: datetime,
    statuses: Sequence[SourceStatus],
    counts: dict[str, EmittedStats],
) -> int:
    """소스별 실행 요약. 0건이어도 낸다(팀 발행 규약 4).

    `counts` 는 장부의 발급 실행으로 집계한 소스별 건수와 가장 오래된 수집 시각이다.
    앞 시도에서 발급된 행도 같은 실행의 통계에 포함되므로 재시도해도 값이 유지된다.
    발급 시각 구간으로 집계하지 않아 가까운 다른 실행의 발급분은 섞이지 않는다.
    """
    for status in statuses:
        publisher.publish(
            status.source,
            run_summary_event(
                source=status.source,
                domain=status.domain,
                run_id=run_id,
                logical_date=logical_date,
                status=status.status,
                outcome=status.outcome,
                emitted=counts.get(status.source, EmittedStats(0, None)),
                failure_reason=status.failure_reason,
            ),
        )
    publisher.flush()
    return len(statuses)
