"""수집 이벤트 봉투. 토픽마다 한 모양만 흐른다.

| 토픽 | 이벤트 | event_id |
|---|---|---|
| raw-file-ready | 기사 | {source}-{article_id} |
| collect-run-summary | 소스별 실행 요약 | {source}-{run_id} |

요약은 0건과 장애를 구별하고, 수집 결과와 밀린 기사 발급을 따로 센다.
소비자가 아직 없는 이행 시점이라 schema_version은 1을 유지한다(S15P21A102-205·206).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from trendin.common.collect.ledger import EmittedStats, PendingArticle

if TYPE_CHECKING:
    from trendin.common.collect.flow import SourceOutcome

SCHEMA_VERSION = 1
KST = timezone(timedelta(hours=9), "KST")


def _kst(value: datetime) -> str:
    """이벤트 timestamp 는 ISO-8601 · KST 오프셋 (팀 계약 시각 규약)."""
    return value.astimezone(KST).isoformat()


def article_event(row: PendingArticle, *, bucket: str, run_id: str) -> dict[str, Any]:
    """기사 하나의 이벤트. `stat` 으로 저장을 확인한 뒤에만 만든다.

    `collected_at` 은 **그 기사를 받은 시각**이지 이번 실행의 시각이 아니다. 팀 계약이
    `collected_at` 에 요구하는 성질("재처리해도 값이 바뀌지 않는다")을 기사 단위로 옮기면
    이게 된다 — 지난 실행에서 저장만 되고 못 나간 행을 이번에 내도 값이 그대로다.

    `run_id` 는 발급 실행이다. 수집 실행과 다를 수 있고, 수집 시각은
    `collected_at` 이 든다. 재발급하면 바뀌므로 파티션 키로 쓰지 않는다.
    `event_id` 는 결정적인 중복 판정 함수다. 파싱해서 source 를 추출하지 않는다.

    본문은 싣지 않는다(불변식 6). `url` · `source_id` · `published_at` 은 저작권법
    제37조 출처 명시라 반드시 있다(불변식 11).
    """
    return {
        "event_id": f"{row.source}-{row.article_id}",
        "schema_version": SCHEMA_VERSION,
        "bucket": bucket,
        "object_key": row.article_key,
        # 팀 봉투에 없던 필드. 추가는 하위 호환이라 schema_version 은 그대로다.
        # 회원 전용 기사는 raw 를 저장하지 않으므로 null 이다 (불변식 2).
        "raw_object_key": row.raw_key,
        "domain": row.domain,
        "source_id": row.source,
        "article_id": row.article_id,
        "run_id": run_id,
        "url": row.url,
        "title": row.title,
        # 소스가 준 오프셋 그대로. 장부가 `published_at_offset` 을 따로 들고 있는 이유다.
        "published_at": row.published_at.isoformat(),
        "collected_at": _kst(row.collected_at),
        "status": "success",
        "record_count": 1,
        # article.json 크기는 장부에 두지 않는다. 소비 측이 대조에 쓰는 건 checksum 이다.
        "size_bytes": None,
        # `object_key` 가 가리키는 객체, 즉 article.json 의 해시다.
        # 장부의 `content_sha256`(raw 의 해시)과 이름만 비슷한 다른 값이다.
        "checksum": f"sha256-{row.article_sha256}",
        "format": "json",
        "compression": "none",
        "failure_reason": None,
        "members_only": row.members_only,
    }


def run_summary_event(
    *,
    source: str,
    domain: str,
    run_id: str,
    logical_date: datetime,
    status: str,
    outcome: SourceOutcome | None,
    emitted: EmittedStats,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """수집 결과는 XCom, 발급 통계는 장부에서 온다. 없는 수집 결과는 0이 아닌 null이다.

    run_started_at은 logical date를 KST로 표기하므로 재시도해도 같다.
    """
    if status not in ("success", "failed"):
        raise ValueError(f"status 는 success 아니면 failed 다: {status!r}")
    if status == "failed" and not failure_reason:
        raise ValueError("failed 이면 failure_reason 을 채운다 (팀 발행 규약 5)")
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": f"{source}-{run_id}",
        "domain": domain,
        "source_id": source,
        "run_id": run_id,
        "run_started_at": _kst(logical_date),
        "status": status,
        "discovered": outcome.discovered if outcome is not None else None,
        "stored": outcome.stored if outcome is not None else None,
        "skipped": outcome.skipped if outcome is not None else None,
        "not_modified": outcome.not_modified if outcome is not None else None,
        "failed": outcome.failed if outcome is not None else None,
        "failed_by_stage": dict(outcome.failed_by_stage) if outcome is not None else None,
        "failures": [asdict(f) for f in outcome.failures] if outcome is not None else None,
        "duration_ms": outcome.duration_ms if outcome is not None else None,
        "members_only_stored": outcome.members_only_stored if outcome is not None else None,
        "emitted": emitted.count,
        "emitted_oldest_collected_at": (
            _kst(emitted.oldest_collected_at) if emitted.oldest_collected_at is not None else None
        ),
        "failure_reason": failure_reason if status == "failed" else None,
    }
