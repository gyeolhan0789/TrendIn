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
from typing import Iterable, Mapping, Protocol, Sequence

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

-- 소비 측이 창을 잘라 읽을 때 쓴다 (S15P21A102-247). **위 부분 인덱스로는 안 된다** —
-- 그쪽은 `event_emitted_at IS NULL` 조건이 붙어 있어서, 그 조건이 없는 질의는 타지 못한다.
-- 장부는 지우지 않으므로(불변식 13) 인덱스가 없으면 회차마다 영원히 자라는 표를 통째로
-- 훑는다. 지금은 행이 적어 티가 안 나고, 티가 날 때쯤이면 원인을 되짚기 어렵다.
--
-- 정렬 칸(`source`·`article_id`)까지 넣지 않는 이유는 창 안의 행이 한 주치뿐이라
-- 그 정렬이 싸기 때문이다. 반면 이 인덱스는 기사를 저장할 때마다 갱신된다.
CREATE INDEX IF NOT EXISTS collected_article_collected_at_idx
    ON collected_article (collected_at);

-- 요약 이벤트가 "이 실행이 발급한 건수" 를 셀 때 쓴다.
CREATE INDEX IF NOT EXISTS collected_article_run_idx
    ON collected_article (domain, event_run_id);

-- 실행 구간으로 세던 시절의 인덱스. 읽는 질의가 없어졌다 (S15P21A102-204).
DROP INDEX IF EXISTS collected_article_emitted_idx;

-- 소스마다 국가 하나 (S15P21A102-276). 국가는 기사가 아니라 **소스의 속성**이라 여기 있다 —
-- `collected_article` 에 칸으로 넣으면 같은 사실이 행마다 수십만 번 복사된다.
--
-- 진실의 자리는 코드의 `SourceDef.country` 고 이 표는 그 거울이다. 뷰가 SQL 안에서 읽어야
-- 하니까 DB 에도 한 벌이 필요하고, `ensure_schema` 가 매 실행 코드 표에서 UPSERT 한다.
--
-- 다른 테이블들과 떨어져 **뷰 바로 앞**에 있는 이유는 뷰가 이 표를 JOIN 하기 때문이다.
-- `collect_validator` 옆(뷰 뒤)으로 옮기면 빈 DB 에서 뷰 생성이 "relation does not exist"
-- 로 죽는다 (2026-09-16 postgres:17 실측). 이미 표가 있는 DB 에서는 안 죽어서, 옮겨 놓고
-- 로컬에서는 멀쩡한 채로 넘어가기 쉽다.
CREATE TABLE IF NOT EXISTS collect_source_country (
    source  text PRIMARY KEY,
    country text NOT NULL
);

-- 소비 측(Spark `ingest`)이 읽는 단 하나의 창구다 (S15P21A102-247).
--
-- **이 뷰의 칸이 곧 이벤트 봉투다.** Kafka 로 나가던 `events.article_event()` 의 결과와
-- 같은 값을 같은 이름으로 낸다. 소비 측은 `collected_article` 을 직접 보지 않으므로, 표의
-- 칸 이름이 바뀌면 여기 정의만 고치면 되고 저쪽은 모르고 지나간다 — 남의 표를 직접 읽을
-- 때 생기는 "조용히 깨진다" 를 이 한 겹이 막는다.
--
-- `published_at` 을 문자열로 내는 이유는 오프셋이다. `timestamptz` 는 순간만 보관하고
-- 소스가 준 표기를 버리므로 `published_at_offset` 으로 되살려 ISO-8601 로 굳힌다
-- (`restore_offset` 이 파이썬에서 하던 일과 같다). 팀 시각 규약이 `published_at` 을
-- "소스가 준 시각을 그대로 보존" 으로 못 박아서, 되살리지 않으면 그 규약이 깨진다.
--
-- **소수점 이하를 조건부로 붙인다.** `isoformat()` 은 마이크로초가 0 이면 아예 생략하는데,
-- `to_char` 로 `.US` 를 늘 붙이면 같은 행이 옛 봉투와 다른 문자열이 된다. 값은 같지만
-- 계약이 적어 둔 표기와 갈리므로 여기서 맞춘다. 늘 생략하는 쪽은 안 된다 — `collected_at`
-- 은 수집기가 `now()` 로 찍어서 마이크로초가 실제로 있다.
--
-- `source_country` 는 이 뷰가 **다른 표를 읽는 유일한 자리**다 (S15P21A102-276). 읽는 표가
-- 수집이 소유한 `collect_source_country` 라서 남의 스키마에 묶이지 않는다. 기사가 아니라
-- 소스의 속성이므로 장부 행에 복사하지 않고 여기서 붙인다.
--
-- `collected_at` 은 KST 다. 발급 봉투가 그랬고 KST 는 서머타임이 없어 늘 `+09:00` 이다.
-- 창을 자를 때 쓰는 값은 `collected_at_ts` 로 따로 낸다 — 문자열로 범위를 자르면
-- 인덱스를 못 탄다.
--
-- `CREATE OR REPLACE` 라서 소비 측이 읽는 중에도 끊기지 않는다. 칸 목록이 바뀌면 이
-- 문장이 실패하므로 그때는 사람이 DROP 후 재생성한다.
--
-- ⚠️ **새 칸은 맨 뒤에만 붙는다.** PostgreSQL 의 `CREATE OR REPLACE VIEW` 는 칸을 덧붙이는
-- 것만 허용하고, 중간에 끼우면 뒤 칸의 이름을 바꾸는 것으로 읽어 거절한다
-- (`cannot change name of view column ... to ...`, 2026-09-16 postgres:17 실측).
-- 그래서 `source_country` 가 뜻으로는 봉투 칸인데도 창 자르기용 `collected_at_ts` 뒤에
-- 있다. 뜻에 맞게 앞으로 옮기려면 이미 뷰가 있는 DB 마다 사람이 DROP 을 해야 하고, 그동안
-- 수집 DAG 의 첫 태스크가 매 회차 실패한다.
CREATE OR REPLACE VIEW collected_article_event AS
SELECT
    source || '-' || article_id AS event_id,
    domain,
    source      AS source_id,
    article_id,
    article_key AS object_key,
    raw_key     AS raw_object_key,
    url,
    title,
    to_char(published_local, 'YYYY-MM-DD"T"HH24:MI:SS')
        || CASE
               WHEN mod(date_part('microseconds', published_local)::bigint, 1000000) = 0 THEN ''
               ELSE '.' || lpad(
                   mod(date_part('microseconds', published_local)::bigint, 1000000)::text, 6, '0')
           END
        || CASE WHEN published_offset < 0 THEN '-' ELSE '+' END
        || lpad((abs(published_offset) / 60)::text, 2, '0')
        || ':'
        || lpad(mod(abs(published_offset), 60)::text, 2, '0')
        AS published_at,
    to_char(collected_local, 'YYYY-MM-DD"T"HH24:MI:SS')
        || CASE
               WHEN mod(date_part('microseconds', collected_local)::bigint, 1000000) = 0 THEN ''
               ELSE '.' || lpad(
                   mod(date_part('microseconds', collected_local)::bigint, 1000000)::text, 6, '0')
           END
        || '+09:00'
        AS collected_at,
    'sha256-' || article_sha256 AS checksum,
    members_only,
    collected_at AS collected_at_ts,
    coalesce(country, 'XX') AS source_country
FROM (
    -- 시각 계산을 한 번만 한다. 포맷 식이 같은 값을 세 번 읽어서, 여기서 묶지 않으면
    -- 오프셋 식이 여섯 번 되풀이되고 한 곳만 고쳐지는 날이 온다.
    SELECT
        a.*,
        c.country,
        coalesce(a.published_at_offset, 0)::int AS published_offset,
        a.published_at AT TIME ZONE make_interval(
            mins => coalesce(a.published_at_offset, 0)) AS published_local,
        a.collected_at AT TIME ZONE 'Asia/Seoul' AS collected_local
      FROM collected_article a
      -- `LEFT JOIN` 이라 참조 표에 없는 소스도 행이 사라지지 않는다. 그런 행은 바깥에서
      -- `XX` 가 되고, 참조 표가 생기기 전에 받아 둔 기사도 소급 채우기 없이 국가를 얻는다.
      LEFT JOIN collect_source_country c ON c.source = a.source
) a;

CREATE TABLE IF NOT EXISTS collect_validator (
    url           text        PRIMARY KEY,
    etag          text,
    last_modified text,
    updated_at    timestamptz NOT NULL
);
"""

# 코드 표(`SourceDef.country`)를 DB 거울에 맞춘다. `ensure_schema` 가 DDL 뒤에 돌린다.
#
# ⚠️ **DELETE 를 여기 더하지 마라.** `SourceDef` 에서 사라진 소스의 행도 그대로 둔다.
# 지우면 그 소스로 이미 받아 둔 기사가 전부 뷰에서 `XX` 로 바뀌어 과거 집계가 흔들린다.
# 장부는 지우지 않는데(불변식 13) 그 행이 가리키는 국가만 사라지는 셈이다.
# "표를 코드와 맞춰야지" 하고 지우는 것이 정확히 막으려는 일이다.
_UPSERT_SOURCE_COUNTRY = """
INSERT INTO collect_source_country (source, country)
VALUES (%s, %s)
ON CONFLICT (source) DO UPDATE SET country = EXCLUDED.country
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


@dataclass(frozen=True, slots=True)
class EmittedStats:
    """발급 실행별 기사 수와 가장 오래된 수집 시각. 수집 지연과 발급 지연을 구분한다."""

    count: int
    oldest_collected_at: datetime | None


class Ledger(Protocol):
    """장부. 발견과 취득 사이, 저장과 발급 사이에 끼어드는 두 자리를 연다."""

    def ensure_schema(self, countries: Mapping[str, str]) -> None:
        """장부가 쓰는 표와 뷰를 만들고, 소스→국가 참조 표를 코드 표에 맞춘다.

        `countries` 는 `SourceDef.country` 를 소스 키로 모은 것이다. 인자로 받는 이유는
        장부가 소스 레지스트리를 모르기 때문이다 — 여기서 import 하면 공통 계층이 도메인
        패키지를 거꾸로 알게 된다.

        여러 번 돌려도 같은 끝 상태여야 한다. DAG 첫 태스크가 매 회차 부른다.
        """
        ...

    def source_countries(self) -> dict[str, str]:
        """소스→국가 거울을 통째로 돌려준다. 발급 봉투의 `source_country` 가 여기서 온다.

        **코드의 `SourceDef` 를 대신 읽으면 뷰와 갈린다.** 거울은 소스가 레지스트리에서
        사라져도 지우지 않으므로(`_UPSERT_SOURCE_COUNTRY` 의 경고), 그 소스의 미발급 행이
        장부에 남아 있으면 코드 표에는 없고 거울에는 있는 상태가 된다. 뷰는 거울을 읽으니
        발급도 거울을 읽어야 같은 기사에 같은 국가가 붙는다.

        소스마다 묻지 않고 전량을 주는 이유는 부르는 자리가 만 건을 도는 루프 앞이라서다.
        소스 수는 한 자리라 전량이 싸다.
        """
        ...

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

    def mark_emitted_many(
        self, keys: Sequence[tuple[str, str]], at: datetime, run_id: str
    ) -> None:
        """발급된 행을 한 번에 적는다. 발급 성공 뒤에만 부른다(at-least-once).

        묶음으로 받는 이유는 트랜잭션이다. 행마다 열면 만 건에 만 번이고, 중간에 죽으면
        절반만 적힌 채로 남는다. 한 트랜잭션이면 다 적히거나 하나도 안 적힌다.

        `run_id` 는 어느 실행이 냈는지다. 요약 건수를 이 값으로 센다.
        """
        ...

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, EmittedStats]:
        """그 실행이 발급한 기사 수를 소스별로 센다. 요약 이벤트의 `emitted` 와 발급 지연의 근거다.

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
        # 뷰의 `LEFT JOIN` 이 읽는 참조 표에 해당한다. 만들 표가 없으니 이것만 남는다.
        self.countries: dict[str, str] = {}

    def ensure_schema(self, countries: Mapping[str, str]) -> None:
        """Postgres 쪽 UPSERT 와 같은 일을 한다 — 덮어쓰기만 하고 지우지 않는다."""
        self.countries.update(countries)

    def source_countries(self) -> dict[str, str]:
        """사본을 준다 — 받은 쪽이 고쳐도 거울이 흔들리지 않게."""
        return dict(self.countries)

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

    def mark_emitted_many(
        self, keys: Sequence[tuple[str, str]], at: datetime, run_id: str
    ) -> None:
        for key in keys:
            self._emitted[key] = (at, run_id)

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, EmittedStats]:
        stats: dict[str, EmittedStats] = {}
        for key, (at, emitted_run) in self._emitted.items():
            row = self._rows[key]
            if row.domain == domain and emitted_run == run_id and at is not None:
                previous = stats.get(row.source, EmittedStats(0, None))
                oldest = previous.oldest_collected_at
                stats[row.source] = EmittedStats(
                    previous.count + 1,
                    min(oldest, row.collected_at) if oldest is not None else row.collected_at,
                )
        return stats


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

_SELECT_SOURCE_COUNTRY = """
SELECT source, country FROM collect_source_country
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
SELECT source, count(*), min(collected_at)
FROM collected_article
WHERE domain = %s AND event_run_id = %s AND event_emitted_at IS NOT NULL
GROUP BY source
"""


class PostgresLedger:
    """앱 DB 의 장부. 접속은 `Database` 로 받는다 (Connection ID `app_db` 의 값)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def ensure_schema(self, countries: Mapping[str, str]) -> None:
        """DDL 을 멱등하게 적용하고 소스→국가 참조 표를 코드 표에 맞춘다. DAG 첫 태스크가 부른다.

        DDL 과 UPSERT 가 한 트랜잭션이다. 표가 생겼는데 값이 안 들어간 중간 상태로 끝나면
        그 회차의 뷰가 전건 `XX` 를 낸다.
        """
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(DDL)
            # 순서를 고정한다. 매 회차 같은 문장이 같은 차례로 나가야 로그를 견줄 수 있다.
            for source, country in sorted(countries.items()):
                cur.execute(_UPSERT_SOURCE_COUNTRY, (source, country))

    def source_countries(self) -> dict[str, str]:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_SOURCE_COUNTRY)
            return dict(cur.fetchall())

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

    def mark_emitted_many(
        self, keys: Sequence[tuple[str, str]], at: datetime, run_id: str
    ) -> None:
        if not keys:
            return
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE collected_article SET event_emitted_at = %s, event_run_id = %s "
                "WHERE (source, article_id) IN %s",
                (at, run_id, tuple(keys)),
            )

    def emitted_by_run(self, domain: str, run_id: str) -> dict[str, EmittedStats]:
        with self._db.transaction() as conn, conn.cursor() as cur:
            cur.execute(_SELECT_EMITTED_BY_RUN, (domain, run_id))
            return {source: EmittedStats(count, oldest) for source, count, oldest in cur.fetchall()}
