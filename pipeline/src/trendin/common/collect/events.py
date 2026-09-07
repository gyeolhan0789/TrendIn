"""이벤트 봉투 (설계 문서 #6).

**팀 계약(`docs/data-pipeline-design.md` 5장)의 필드명을 그대로 쓴다.** 팀 계약은 배치
하나에 이벤트 하나를 전제로 짜였고 우리는 기사 하나에 이벤트 하나를 낸다. 그래서 토픽
`raw-file-ready` 에 모양이 둘 흐른다.

| | 기사 이벤트 | 실행 요약 이벤트 |
|---|---|---|
| `event_id` | `{source}-{article_id}` | `{source}-{run_id}` |
| `object_key` | article.json 키 | `null` |
| 소비 측 구분 | `object_key` 가 있다 | `object_key` 가 `null` 이다 |

요약 이벤트를 남긴 이유는 팀 발행 규약 4·5(0건·실패에도 이벤트를 낸다)가 있는 이유,
즉 "소비 측이 누락과 실패를 구분할 수 있어야 한다" 때문이다. 기사 이벤트만 내면 0건과
장애가 똑같이 "아무것도 안 옴" 으로 보인다.

**두 모양 다 팀 봉투의 필드를 하나도 빼지 않는다.** 안 쓰는 칸은 `null` 로 둔다. 빼면
"제거·타입 변경은 `schema_version` 을 올린다"에 걸리는데, 우리가 한 건 모양을 하나 더한
것이지 계약을 올린 게 아니다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from trendin.common.collect.ledger import PendingArticle

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

    `run_id` 는 **이 기사를 발급한 실행**이다. 수집한 실행이 아니다 — 저장만 되고 못
    나간 행은 다음 실행이 내므로 둘이 갈리고, 그게 정상이다. 소비 측이 이 값으로 curated
    를 파티션하고(`domain/published_date/source/run_id`) 재처리 단위를 자르기 때문에
    비워 둘 수 없다. "기사를 언제 받았나"는 `collected_at` 이 따로 든다.

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
    record_count: int,
    bucket: str,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """소스 하나의 이번 실행 결과. `object_key` 가 `null` 이라 기사 이벤트와 갈린다.

    `collected_at` 은 logical date 라 재시도해도 값이 같다(팀 계약 필드 규약).
    `record_count` 는 **이 실행이 발급한 기사 수**다. 장부를 실행 구간으로 다시 세면
    실행이 겹칠 때 앞 실행이 낸 것까지 제 몫으로 세어 통계가 부푼다. 태스크 재시도는
    `publish_pending` 이 이미 나간 행을 다시 세지 않으므로 값이 흔들리지 않는다.
    """
    if status not in ("success", "failed"):
        raise ValueError(f"status 는 success 아니면 failed 다: {status!r}")
    if status == "failed" and not failure_reason:
        raise ValueError("failed 이면 failure_reason 을 채운다 (팀 발행 규약 5)")
    return {
        "event_id": f"{source}-{run_id}",
        "schema_version": SCHEMA_VERSION,
        "bucket": bucket,
        "object_key": None,
        "raw_object_key": None,
        "domain": domain,
        "source_id": source,
        "article_id": None,
        "run_id": run_id,
        "url": None,
        "title": None,
        "published_at": None,
        "collected_at": _kst(logical_date),
        "status": status,
        "record_count": record_count,
        "size_bytes": None,
        "checksum": None,
        "format": None,
        "compression": None,
        "failure_reason": failure_reason,
        "members_only": None,
    }
