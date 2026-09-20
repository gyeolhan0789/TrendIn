"""기사 이벤트 봉투의 **정본**.

**이 함수는 이제 아무것도 발행하지 않는다.** 브로커를 걷으면서(Kafka 제거 3/3) 봉투를
만드는 자리가 파이썬에서 SQL 로 넘어갔다 — 소비 측이 읽는 것은 `ledger.DDL` 의
`collected_article_event` 뷰다. 그런데도 이 파일이 남아 있는 이유는 **그 뷰가 맞다는 것을
무엇엔가 대조해야** 하기 때문이다. 뷰의 `published_at` 은 `to_char` · `lpad` · `make_interval`
로 조립한 문자열이고, 여기 `isoformat()` 과 한 글자라도 다르면 소비 측 계약이 조용히 갈린다.

대조하는 자리는 둘이다 — `tests/common/test_ledger_view.py`(진짜 PostgreSQL 에 뷰를 걸고
칸마다 값을 맞춘다)와 `tests/common/test_contract_fixtures.py`(소비 측이 쓰는
`spark/tests/fixtures/contract/` 를 여기서 다시 만들어 맞춘다).

`schema_version` 은 1 이다. 봉투의 칸이 바뀐 적이 없다 (S15P21A102-205·206).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from trendin.common.collect.ledger import LedgerRow

SCHEMA_VERSION = 1
KST = timezone(timedelta(hours=9), "KST")


def _kst(value: datetime) -> str:
    """이벤트 timestamp 는 ISO-8601 · KST 오프셋 (팀 계약 시각 규약)."""
    return value.astimezone(KST).isoformat()


def article_event(
    row: LedgerRow, *, bucket: str, run_id: str, source_country: str
) -> dict[str, Any]:
    """장부 행 하나가 소비 측에 보이는 모양.

    `collected_at` 은 **그 기사를 받은 시각**이다. 팀 계약이 `collected_at` 에 요구하는
    성질("재처리해도 값이 바뀌지 않는다")을 기사 단위로 옮기면 이게 된다 — 언제 읽히든
    값이 그대로다.

    `run_id` 는 발급이 있던 시절의 칸이다. 발급이 없어졌으므로 뷰는 이 칸을 내지 않고
    소비 측이 `None` 으로 채운다 (`spark/ingest/collected.py`). 여기 남아 있는 것은
    fixture 가 그 시절 봉투의 모양을 그대로 보존하기 때문이다.
    `event_id` 는 결정적인 중복 판정 함수다. 파싱해서 source 를 추출하지 않는다.

    `source_country` 를 인자로 받는 이유는 그 값이 기사가 아니라 **소스**의 속성이라
    `LedgerRow` 에 없기 때문이다(`bucket` 과 같은 사정이다).

    본문은 싣지 않는다(불변식 6). `url` · `source_id` · `published_at` 은 저작권법
    제37조 출처 명시라 반드시 있다(불변식 11).
    """
    return {
        "event_id": f"{row.source}-{row.article_id}",
        "schema_version": SCHEMA_VERSION,
        "bucket": bucket,
        "object_key": row.article_key,
        # 팀 봉투에 없던 필드. 추가는 하위 호환이라 schema_version 은 그대로다.
        # 회원 전용·유료 표시 기사는 raw 를 저장하지 않으므로 null 이다 (불변식 2).
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
        "paywalled": row.paywalled,
        # 소스를 발행하는 법인이 있는 나라 (S15P21A102-276). 이 함수가 봉투의 정본이고
        # 장부 뷰가 그것을 흉내 내므로, 여기 넣지 않으면 뷰만 칸을 낸 꼴이 된다 —
        # `tests/common/test_ledger_view.py` 가 둘을 대조한다.
        "source_country": source_country,
    }
