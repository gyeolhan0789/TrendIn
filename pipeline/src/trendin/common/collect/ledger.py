"""수집 장부 (설계 문서 #5.4, S15P21A102-166).

장부가 있는 이유는 "저장이 확인된 뒤에 발급한다"를 **재시도에도** 성립하게 만드는 자리가
필요해서다. 저장 태스크가 여기 적고 발급 태스크가 여기서 읽는다. 둘 사이에서 죽어도
`event_emitted_at` 이 비어 있으니 다음 실행이 이어 낸다(#4).

같은 기사를 다시 받지 않는 판정(불변식 12)도 여기서 한다. 그 판정을 어댑터가 흉내 내면
"그 실행에서 방금 본 id 만 아는" 반쪽짜리가 장부와 두 벌로 남는다.

들어오는 값은 `Article`(어댑터의 출력) 그대로고, 나가는 값은 `PendingArticle`(발급 봉투를
채울 만큼만)이다. 방향이 다르니 모양도 다르다.

이 모듈은 airflow 를 import 하지 않는다 — 태스크 함수는 Airflow 없이 테스트한다
(README 규약 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Protocol

from trendin.common.collect.article import Article
from trendin.common.collect.db import Database

# 앱 DB 에 마이그레이션 도구가 없다 — `docker/postgres-init/` 은 빈 볼륨 초기화 때 한 번만
# 돌아서 이미 있는 DB 에는 안 먹고, backend 는 `ddl-auto: create` 로 스키마를 다시 만든다.
# 그래서 DAG 첫 태스크가 이 DDL 을 멱등하게 적용한다. 원문은 설계 문서 #5.4 에도 있다.
#
# `collected_article` 은 JPA 밖의 테이블이고 지우지 않는다(불변식 13). 그 합의가
# S15P21A102-12(DB 초기 스키마)에 적혀야 한다.
DDL = """
CREATE TABLE IF NOT EXISTS collected_article (
    source              text        NOT NULL,
    article_id          text        NOT NULL,
    domain              text        NOT NULL,
    route               text        NOT NULL,
    url                 text        NOT NULL,
    title               text        NOT NULL,
    published_at        timestamptz NOT NULL,
    published_at_offset smallint,
    raw_key             text,
    article_key         text        NOT NULL,
    content_sha256      text,
    article_sha256      text        NOT NULL,
    members_only        boolean     NOT NULL DEFAULT false,
    collected_at        timestamptz NOT NULL,
    event_emitted_at    timestamptz,
    event_run_id        text,
    PRIMARY KEY (source, article_id)
);

-- 이 브랜치 전에 만들어진 테이블에도 칸을 연다. 이미 있으면 아무 일도 없다.
ALTER TABLE collected_article ADD COLUMN IF NOT EXISTS published_at_offset smallint;

-- 어느 실행이 이 행을 발급했나. 요약 이벤트의 건수를 이 값으로 센다 (S15P21A102-204).
ALTER TABLE collected_article ADD COLUMN IF NOT EXISTS event_run_id text;

-- 발급 태스크가 미발급 행만 훑는다. 장부는 계속 자라고 미발급은 늘 소수다.
CREATE INDEX IF NOT EXISTS collected_article_pending_idx
    ON collected_article (domain, collected_at)
    WHERE event_emitted_at IS NULL;

-- 요약 이벤트가 "이 실행이 발급한 건수" 를 셀 때 쓴다.
CREATE INDEX IF NOT EXISTS collected_article_run_idx
    ON collected_article (domain, event_run_id);

-- 실행 구간으로 세던 시절의 인덱스. 읽는 질의가 없어졌다 (S15P21A102-204).
DROP INDEX IF EXISTS collected_article_emitted_idx;

CREATE TABLE IF NOT EXISTS collect_validator (
    url           text        PRIMARY KEY,
    etag          text,
    last_modified text,
    updated_at    timestamptz NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class PendingArticle:
    """발급을 기다리는 장부 행. 발급 봉투(#6)를 채우는 데 필요한 값이 전부 여기 있다.

    발급이 MinIO 를 읽지 않아도 되게 만드는 게 이 모양의 목적이다 — 읽어야 하면 "저장
    확인"의 `stat` 이 `get` 으로 커지고, 미발급이 쌓인 채 재개할 때 그만큼 다시 읽는다.

    `content_sha256`(raw 의 해시)은 여기 없다. 봉투의 `checksum` 은 `object_key` 가
    가리키는 객체, 즉 article.json 의 해시라서다. 이름이 비슷한 다른 값이다.
    """

    source: str
    article_id: str
    domain: str
    url: str
    title: str
    published_at: datetime
    collected_at: datetime
    article_key: str
    article_sha256: str
    raw_key: str | None
    members_only: bool


class Ledger(Protocol):
    """장부. 발견과 취득 사이, 저장과 발급 사이에 끼어드는 두 자리를 연다."""

    def filter_new(self, source: str, article_ids: Iterable[str]) -> set[str]:
        """아직 장부에 없는 id 만 돌려준다.

        소스의 전체 id 를 들고 오지 않는 이유는 장부가 영구라서다(불변식 13). 질의는
        후보 쪽 건수(10~20건)로 묶는다.
        """
        ...

    def record(self, article: Article, *, article_key: str, article_sha256: str) -> bool:
        """저장이 확인된 기사를 적는다. 이미 있으면 아무것도 하지 않고 False.

        멱등이어야 한다 — `(source, article_id)` 하나는 장부 행 하나다(불변식 7).
        """
        ...

    def pending(self, domain: str, limit: int = 500) -> list[PendingArticle]:
        """아직 이벤트가 안 나간 행. 지난 실행에서 저장까지 하고 죽은 행이 여기 딸려 온다.

        도메인으로 자르는 이유는 발급이 DAG 마다 하나씩이라서다 — 안 자르면 dev DAG 이
        fashion 행까지 낸다.
        """
        ...

    def mark_emitted(self, source: str, article_id: str, at: datetime, run_id: str) -> None:
        """발급 성공 뒤에만 부른다. 순서를 뒤집으면 유실이 생긴다(at-least-once).

        `run_id` 는 어느 실행이 냈는지다. 요약 건수를 이 값으로 센다.
        """
        ...

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, int]:
        """그 실행이 발급한 기사 수를 소스별로 센다. 요약 이벤트의 `record_count` 다.

        "이번 시도가 보낸 것" 을 세지 않는 이유는 재시도 때문이다 — 발급까지 마치고 요약
        중간에 죽으면 다음 시도는 보낼 게 없어 0 이 되고, 같은 `event_id` 로 내용이 다른
        요약이 나간다(팀 발행 규약 3 위반). 장부에 적힌 실행으로 세면 흔들리지 않는다.

        실행 구간(`event_emitted_at >= 시작시각`)으로 세지 않는 이유는 겹침이다 — 실행 둘이
        가까우면 앞 실행이 낸 것까지 뒤 실행 몫으로 센다.
        """
        ...

def _offset_minutes(value: datetime) -> int:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError(f"오프셋 없는 시각은 장부에 못 넣는다: {value!r}")
    return int(offset.total_seconds() // 60)


def restore_offset(value: datetime, offset_minutes: int | None) -> datetime:
    """저장할 때 따로 남겨 둔 오프셋으로 소스가 준 표기를 되살린다.

    `timestamptz` 는 순간만 보관하고 오프셋 표기는 버린다. 그래서 그냥 읽으면 한국 매체의
    `+09:00` 이 세션 시간대(보통 UTC)로 바뀌어 나온다. 팀 시각 규약이 `published_at` 을
    "소스가 준 시각을 그대로 보존" 으로 못 박아서, 여기서 되살리지 않으면 이벤트가 그
    규약을 깬다.

    오프셋이 없는 행(이 칸이 생기기 전에 적힌 행)은 읽은 그대로 둔다. 없는 값을 지어내면
    출처가 아니라 추측이 나간다.
    """
    if offset_minutes is None:
        return value
    return value.astimezone(timezone(timedelta(minutes=offset_minutes)))


def to_pending(article: Article, *, article_key: str, article_sha256: str) -> PendingArticle:
    """`Article` 에서 발급에 필요한 값만 뽑는다. 장부를 거치지 않는 경로도 같은 모양을 쓴다."""
    return PendingArticle(
        source=article.source,
        article_id=article.article_id,
        domain=article.domain,
        url=article.url,
        title=article.title,
        published_at=article.published_at,
        collected_at=article.collected_at,
        article_key=article_key,
        article_sha256=article_sha256,
        raw_key=article.raw_key,
        members_only=bool(article.members_only),
    )


class InMemoryLedger:
    """프로세스가 사는 동안만 기억한다. 테스트와 백필 예행 연습용이다.

    실행 사이에 남지 않으므로 주기 실행에 쓰면 매번 전량을 다시 받는다(불변식 12 위반).
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], PendingArticle] = {}
        self._emitted: dict[tuple[str, str], tuple[datetime, str]] = {}

    def filter_new(self, source: str, article_ids: Iterable[str]) -> set[str]:
        return {aid for aid in article_ids if (source, aid) not in self._rows}

    def record(self, article: Article, *, article_key: str, article_sha256: str) -> bool:
        key = (article.source, article.article_id)
        if key in self._rows:
            return False
        self._rows[key] = to_pending(
            article, article_key=article_key, article_sha256=article_sha256
        )
        return True

    def pending(self, domain: str, limit: int = 500) -> list[PendingArticle]:
        rows = [
            r for k, r in self._rows.items() if k not in self._emitted and r.domain == domain
        ]
        rows.sort(key=lambda r: (r.collected_at, r.source, r.article_id))
        return rows[:limit]

    def mark_emitted(self, source: str, article_id: str, at: datetime, run_id: str) -> None:
        self._emitted[(source, article_id)] = (at, run_id)

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for key, (at, emitted_run) in self._emitted.items():
            row = self._rows[key]
            if row.domain == domain and emitted_run == run_id and at is not None:
                counts[row.source] = counts.get(row.source, 0) + 1
        return counts


_INSERT = """
INSERT INTO collected_article (
    source, article_id, domain, route, url, title, published_at, published_at_offset,
    raw_key, article_key, content_sha256, article_sha256, members_only, collected_at
) VALUES (
    %(source)s, %(article_id)s, %(domain)s, %(route)s, %(url)s, %(title)s,
    %(published_at)s, %(published_at_offset)s,
    %(raw_key)s, %(article_key)s, %(content_sha256)s, %(article_sha256)s,
    %(members_only)s, %(collected_at)s
)
ON CONFLICT (source, article_id) DO NOTHING
"""

_SELECT_PENDING = """
SELECT source, article_id, domain, url, title, published_at, published_at_offset,
       collected_at, article_key, article_sha256, raw_key, members_only
FROM collected_article
WHERE event_emitted_at IS NULL AND domain = %s
ORDER BY collected_at, source, article_id
LIMIT %s
"""


# `event_emitted_at IS NOT NULL` 이 붙는 이유는 재발행 때문이다. 발급 표시만 지우고
# `event_run_id` 를 남기면 아직 안 나간 행이 옛 실행 몫으로 잡힌다.
_SELECT_EMITTED_BY_RUN = """
SELECT source, count(*)
FROM collected_article
WHERE domain = %s AND event_run_id = %s AND event_emitted_at IS NOT NULL
GROUP BY source
"""


class PostgresLedger:
    """앱 DB 의 장부. 접속은 `Database` 로 받는다 (Connection ID `app_db` 의 값)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def ensure_schema(self) -> None:
        """DDL 을 멱등하게 적용한다. DAG 의 첫 태스크가 부른다."""
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(DDL)

    def filter_new(self, source: str, article_ids: Iterable[str]) -> set[str]:
        ids = list(dict.fromkeys(article_ids))
        if not ids:
            return set()
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT article_id FROM collected_article "
                "WHERE source = %s AND article_id = ANY(%s)",
                (source, ids),
            )
            known = {r[0] for r in cur.fetchall()}
        return {aid for aid in ids if aid not in known}

    def record(self, article: Article, *, article_key: str, article_sha256: str) -> bool:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                _INSERT,
                {
                    "source": article.source,
                    "article_id": article.article_id,
                    "domain": article.domain,
                    "route": article.route,
                    "url": article.url,
                    "title": article.title,
                    "published_at": article.published_at,
                    "published_at_offset": _offset_minutes(article.published_at),
                    "raw_key": article.raw_key,
                    "article_key": article_key,
                    "content_sha256": article.content_sha256,
                    "article_sha256": article_sha256,
                    "members_only": bool(article.members_only),
                    "collected_at": article.collected_at,
                },
            )
            return cur.rowcount == 1

    def pending(self, domain: str, limit: int = 500) -> list[PendingArticle]:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_PENDING, (domain, limit))
            rows = cur.fetchall()
        return [
            PendingArticle(
                source=r[0],
                article_id=r[1],
                domain=r[2],
                url=r[3],
                title=r[4],
                published_at=restore_offset(r[5], r[6]),
                collected_at=r[7],
                article_key=r[8],
                article_sha256=r[9],
                raw_key=r[10],
                members_only=r[11],
            )
            for r in rows
        ]

    def mark_emitted(self, source: str, article_id: str, at: datetime, run_id: str) -> None:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE collected_article SET event_emitted_at = %s, event_run_id = %s "
                "WHERE source = %s AND article_id = %s",
                (at, run_id, source, article_id),
            )

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, int]:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_EMITTED_BY_RUN, (domain, run_id))
            return {r[0]: r[1] for r in cur.fetchall()}
