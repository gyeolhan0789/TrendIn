"""장부 뷰를 진짜 PostgreSQL 에 걸고 발급 봉투와 맞춰 본다 (S15P21A102-247).

**문자열 검사로는 못 잡는 것을 잡는다.** `test_ledger.py` 의 뷰 검사는 DDL 에 낱말이 있는지만
본다. 그런데 뷰가 내는 `published_at` 은 `to_char` · `date_part` · `lpad` · `make_interval` 로
조립한 문자열이고, 그것이 `events.article_event()` 가 내던 `isoformat()` 과 **한 글자라도**
다르면 소비 측 계약이 조용히 갈린다. 그 비교는 SQL 을 실제로 돌려야만 할 수 있다.

토픽이 걷히면서 봉투를 만드는 자리가 파이썬에서 SQL 로 넘어갔다. 그 이사가 값을 바꾸지
않았다는 근거가 이 파일이다 — `article_event()` 가 정본이고 뷰가 그것을 흉내 낸다.

**DB 가 있을 때만 돈다.** 없으면 통째로 건너뛴다.

    docker run -d --rm --name trendin-test-pg -e POSTGRES_PASSWORD=test \\
      -p 55433:5432 postgres:17
    TRENDIN_TEST_DB_URL=postgresql://postgres:test@127.0.0.1:55433/postgres \\
      .venv/bin/pytest tests/common/test_ledger_view.py
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.article import Article
from trendin.common.collect.db import Database
from trendin.common.collect.events import article_event
from trendin.common.collect.ledger import PostgresLedger, to_pending

DB_URL_ENV = "TRENDIN_TEST_DB_URL"

pytestmark = pytest.mark.skipif(
    not os.environ.get(DB_URL_ENV, "").strip(),
    reason=f"{DB_URL_ENV} 가 없다 — 진짜 PostgreSQL 이 있어야 뷰를 돌려 볼 수 있다",
)

KST = timezone(timedelta(hours=9))
# 뷰가 `LEFT JOIN` 으로 읽는 참조 표의 내용. 이 파일의 기사는 전부 vogue 다.
COUNTRIES = {"vogue": "KR"}
BUCKET = "raw-data"
RUN_ID = "20260903T110000"
SHA = "a" * 64

# 뷰가 내는 칸 중 **봉투와 같아야 하는 것.** `collected_at_ts` 는 창을 자르는 데만 쓰고
# 봉투에 안 들어간다. 소비 측도 같은 목록을 자기 자리에 들고 있다
# (`spark/src/.../ingest/collected.VIEW_COLUMNS`) — 계약의 양 끝을 각자 고정한다.
SHARED = (
    "event_id",
    "domain",
    "source_id",
    "article_id",
    "object_key",
    "raw_object_key",
    "url",
    "title",
    "published_at",
    "collected_at",
    "checksum",
    "members_only",
    # 뷰에서는 `collected_at_ts` 뒤에 있다 — `CREATE OR REPLACE VIEW` 가 칸을 덧붙이는 것만
    # 허용해서다. 여기서는 읽는 차례가 아니라 **봉투와 같아야 하는 칸**을 모으는 목록이라
    # 뜻이 같은 것끼리 둔다.
    "source_country",
    "paywalled",
)


def make_article(
    *,
    article_id: str = "854414",
    published_at: datetime,
    collected_at: datetime,
    members_only: bool = False,
    paywalled: bool = False,
    source: str = "vogue",
) -> Article:
    """`tests/common/test_events.py` 의 `pending()` 과 같은 값으로 둔다.

    두 곳이 갈리면 같은 계약을 두 모양으로 설명하는 셈이 된다
    (`scripts/gen-contract-fixtures.py` 가 둔 규약).
    """
    return Article(
        domain="fashion",
        source=source,
        route="rss",
        article_id=article_id,
        url=f"https://www.vogue.co.kr/2026/09/03/{article_id}/",
        title="제목",
        published_at=published_at,
        collected_at=collected_at,
        raw_key=(
            None
            if members_only or paywalled
            else f"fashion/{source}/rss/2026/09/03/{article_id}/raw.xml"
        ),
        content_sha256=None if members_only or paywalled else "c" * 64,
        members_only=members_only or None,
        paywalled=paywalled or None,
    )


@pytest.fixture
def ledger():
    """빈 장부와 뷰. 테이블을 비우고 시작해 테스트끼리 섞이지 않게 한다."""
    db = Database(os.environ[DB_URL_ENV].strip())
    store = PostgresLedger(db)
    # 빈 매핑으로 한 번 — 표만 만들고 아무것도 적지 않는다. 참조 표는 UPSERT 만 하고
    # 지우지 않으므로(`ledger._UPSERT_SOURCE_COUNTRY` 의 경고) 비우지 않으면 앞 테스트가
    # 넣은 행이 남는다.
    store.ensure_schema({})
    with db.transaction() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE collected_article")
        cur.execute("TRUNCATE collect_source_country")
    store.ensure_schema(COUNTRIES)
    return store, db


def country_rows(db: Database) -> dict:
    with db.transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT source, country FROM collect_source_country")
        return dict(cur.fetchall())


def view_row(db: Database) -> dict:
    with db.transaction() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {', '.join(SHARED)} FROM collected_article_event")
        rows = cur.fetchall()
    assert len(rows) == 1, f"행이 하나여야 한다: {rows!r}"
    return dict(zip(SHARED, rows[0]))


def envelope(article: Article) -> dict:
    """`article_event()` 가 내던 값. 뷰가 맞춰야 하는 정본이다."""
    full = article_event(
        to_pending(article, article_key=key_of(article), article_sha256=SHA),
        bucket=BUCKET,
        run_id=RUN_ID,
        # 참조 표에 없는 소스는 뷰가 `XX` 를 내므로 봉투 쪽도 같은 기본값을 쓴다.
        source_country=COUNTRIES.get(article.source, "XX"),
    )
    return {name: full[name] for name in SHARED}


def key_of(article: Article) -> str:
    return f"fashion/{article.source}/rss/2026/09/03/{article.article_id}/article.json"


def store(ledger, article: Article) -> None:
    ledger.record(article, article_key=key_of(article), article_sha256=SHA)


# --- 값이 같은가 -----------------------------------------------------------


def test_뷰가_발급_봉투와_같은_값을_낸다(ledger):
    """이 파일이 있는 이유. 하나라도 다르면 소비 측이 다른 것을 받는다."""
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    assert view_row(db) == envelope(article)


def test_마이크로초가_있는_수집_시각도_같다(ledger):
    """`collected_at` 은 수집기가 `now()` 로 찍어서 마이크로초가 실제로 들어 있다.

    뷰가 `.US` 를 무조건 붙이면 마이크로초 0 인 행에서 `isoformat()` 과 갈리고, 늘 생략하면
    이 경우에 정밀도를 버린다. 그래서 두 경우를 다 본다.
    """
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, 30, 123456, tzinfo=timezone.utc),
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["collected_at"].endswith(".123456+09:00")


def test_마이크로초가_0_이면_소수점을_안_붙인다(ledger):
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, 30, tzinfo=timezone.utc),
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["collected_at"] == "2026-09-03T11:10:30+09:00"


# --- 오프셋을 되살리는가 ----------------------------------------------------


@pytest.mark.parametrize(
    "offset",
    [
        timedelta(hours=9),  # 한국 매체
        timedelta(0),  # UTC
        timedelta(hours=-5),  # 미국 동부
        timedelta(hours=5, minutes=30),  # 30분 오프셋 — `/60` 과 `mod 60` 이 갈리는 자리
        timedelta(hours=-3, minutes=-30),  # 음수인데 분이 붙는다. 부호를 분에도 따로 못 붙인다
    ],
)
def test_소스가_준_오프셋_표기를_그대로_낸다(ledger, offset: timedelta):
    """`timestamptz` 는 순간만 보관하고 표기를 버린다. 되살리지 않으면 팀 시각 규약
    ("`published_at` 은 소스가 준 시각을 그대로 보존")이 깨진다."""
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=timezone(offset)),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    assert view_row(db)["published_at"] == envelope(article)["published_at"]


def test_발행_시각의_마이크로초도_살아_있다(ledger):
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, 5, 7, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    # 6자리로 0 을 채운다. `lpad` 를 빼면 `.7` 이 되어 값이 십만 배로 읽힌다.
    assert row["published_at"] == "2026-09-03T10:00:05.000007+09:00"


# --- 없는 값을 지어내지 않는가 ----------------------------------------------


def test_회원_전용_기사는_raw_키가_비어_있다(ledger):
    """raw 를 저장하지 않으므로 `raw_object_key` 가 `null` 이다 (불변식 2)."""
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
        members_only=True,
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["raw_object_key"] is None
    assert row["members_only"] is True


def test_유료_표시_기사는_raw_키가_비어_있다(ledger):
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
        paywalled=True,
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["raw_object_key"] is None
    assert (row["members_only"], row["paywalled"]) == (False, True)


def test_checksum_은_article_json_의_해시다(ledger):
    """장부의 `content_sha256`(raw 의 해시)과 바꿔 쓰면 객체 검증이 전건 실패한다."""
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    assert view_row(db)["checksum"] == f"sha256-{SHA}"


# --- 창을 자르는 칸 ---------------------------------------------------------


def test_창은_문자열이_아니라_timestamptz_로_자른다(ledger):
    """`collected_at_ts` 가 따로 있는 이유. 문자열로 범위를 자르면 인덱스를 못 탄다."""
    store_, db = ledger
    collected = datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc)
    store(store_, make_article(published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
                               collected_at=collected))

    with db.transaction() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM collected_article_event WHERE collected_at_ts >= %s",
            (collected - timedelta(hours=1),),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT count(*) FROM collected_article_event WHERE collected_at_ts >= %s",
            (collected + timedelta(hours=1),),
        )
        assert cur.fetchone()[0] == 0


def test_창을_자르는_질의가_인덱스를_탄다(ledger):
    """장부는 지우지 않으므로(불변식 13) 인덱스가 없으면 회차마다 영원히 자라는 표를 훑는다.

    지금은 행이 적어 플래너가 Seq Scan 을 고르는 것이 정상이라, 계획이 아니라 **인덱스가
    실제로 존재하는지**를 DB 에 물어본다. DDL 문자열 검사와 다른 점은 문법이 맞고 칸 이름이
    맞아서 진짜로 만들어졌다는 것까지 본다는 것이다.
    """
    _, db = ledger
    with db.transaction() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'collected_article' AND indexname = %s",
            ("collected_article_collected_at_idx",),
        )
        row = cur.fetchone()

    assert row is not None, "창을 자르는 인덱스가 없다"
    # 부분 인덱스면 `event_emitted_at IS NULL` 이 없는 질의가 타지 못한다.
    assert "WHERE" not in row[0].upper()


# --- 소스 국가 (S15P21A102-276) ----------------------------------------------


def test_뷰가_참조_표에서_소스의_국가를_붙인다(ledger):
    """국가는 소스의 속성이라 장부 행에 없다. 뷰가 `LEFT JOIN` 으로 붙인다."""
    store_, db = ledger
    article = make_article(
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["source_country"] == "KR"


def test_참조_표에_없는_소스는_XX_다(ledger):
    """`LEFT JOIN` 이라 행이 사라지지 않는다. 행이 사라지면 그 기사가 소비 측에서 통째로
    증발하는데, 모르는 국가 하나 때문에 기사를 잃는 것은 훨씬 나쁜 거래다."""
    store_, db = ledger
    article = make_article(
        source="hypebeast",
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)

    row = view_row(db)
    assert row == envelope(article)
    assert row["source_country"] == "XX"


def test_장부가_국가_거울을_진짜로_읽어_온다(ledger):
    """발급이 이 값으로 봉투를 채운다(`flow.publish_pending`). 가짜 DB 로만 보면 SQL 오타가
    안 잡힌다 — 질의가 틀려도 미리 넣어 둔 행이 그대로 돌아온다."""
    store_, _db = ledger

    assert store_.source_countries() == COUNTRIES


def test_레지스트리에서_사라진_소스도_봉투와_뷰가_같은_국가를_낸다(ledger):
    """국가의 정본은 코드의 `SourceDef` 지만 **발급은 거울을 읽는다.**

    거울은 소스가 레지스트리에서 사라져도 지우지 않는다 — 지우면 그 소스로 이미 받아 둔
    기사가 뷰에서 전부 `XX` 가 된다. 그래서 발급이 코드 표를 읽으면 그 소스의 미발급 행에서
    봉투는 `XX`, 뷰는 옛 국가를 내 두 창구가 갈린다.
    """
    store_, db = ledger
    store_.ensure_schema({"hypebeast": "HK"})  # 소스가 레지스트리에 있던 회차
    article = make_article(
        source="hypebeast",
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
    )
    store(store_, article)
    store_.ensure_schema(COUNTRIES)  # hypebeast 를 뺀 회차

    # 발급이 읽는 값과 뷰가 내는 값이 같은 국가를 가리킨다.
    assert store_.source_countries()["hypebeast"] == "HK"
    assert view_row(db)["source_country"] == "HK"




def test_스키마_준비를_두_번_불러도_같은_끝_상태다(ledger):
    """DAG 첫 태스크가 매 회차 부른다. UPSERT 가 아니면 두 번째 호출이 유일키에서 죽는다.

    메모리 구현으로는 이걸 못 본다 — 유일키가 없어 두 번째 쓰기가 그냥 덮어써진다.
    """
    store_, db = ledger
    store_.ensure_schema(COUNTRIES)

    assert country_rows(db) == COUNTRIES


def test_소스가_사라져도_국가_표의_행은_남는다(ledger):
    """`SourceDef` 에서 빠진 소스의 행을 지우면 그 소스로 이미 받아 둔 기사가 뷰에서 전부
    `XX` 로 바뀌어 과거 집계가 흔들린다. 그래서 UPSERT 만 하고 DELETE 는 하지 않는다."""
    store_, db = ledger
    store_.ensure_schema({"hypebeast": "HK"})

    assert country_rows(db) == {"vogue": "KR", "hypebeast": "HK"}


def test_국가가_바뀌면_덮어쓴다(ledger):
    """운영 법인이 바뀌면 코드 표가 정본이고 DB 거울이 따라온다."""
    store_, db = ledger
    store_.ensure_schema({"vogue": "US"})

    assert country_rows(db) == {"vogue": "US"}
