"""`--source ledger` — 수집 장부의 뷰를 읽어 봉투를 만든다 (S15P21A102-247).

**Kafka 를 대신하는 평시 경로다.** 토픽이 나르던 값은 전부 `collected_article` 에서 나온
것이었다 — `common/collect/events.article_event()` 가 그 행의 칸을 하나하나 옮겨 담았고,
`event_id` 도 `{source}-{article_id}` 라 행만 있으면 결정적으로 재생성된다. 그래서
브로커를 걷어내도 소비 측이 잃는 정보가 없다.

**뷰만 읽는다.** `collected_article` 을 직접 보지 않는다. 생산자가 표의 칸 이름을 바꿔도
뷰 정의가 흡수하므로 이쪽이 조용히 깨지지 않는다 — `backfill.py` 가 "소비 측이 생산자
표를 직접 읽는 결합" 을 거절한 이유가 그것이고, 뷰가 그 거절에 대한 답이다.

**창을 겹쳐 읽는다.** "어디까지 읽었나" 를 이 모듈이 들고 있지 않다. 최근 구간을 통째로
읽고 이미 처리한 것은 처리 이력이 거른다 (중복 차단 2, `io/ledger.py`). 실시간이 요건이
아니라서 이 편이 낫다 — checkpoint 라는 두 번째 상태를 만들지 않는다. 창이 짧아 빠뜨리는
쪽이 겹쳐 읽는 쪽보다 훨씬 나쁘므로 기본값을 넉넉하게 둔다.

**행을 드라이버로 모은다.** Spark JDBC 로 읽지 않고 평범한 연결로 읽는다. 회차당 수백
건이라 나눠 읽을 이유가 없고, `backfill.envelope_frame` 이 이미 같은 방식으로 봉투 목록을
프레임으로 만들기 때문에 두 경로가 같은 조립부를 쓴다.

**계약 판별은 건너뛰지 않는다.** 백필은 `classify` 를 태우지 않는데, 그 이유는 재구성한
봉투에 `url`·`published_at` 이 없어 전량이 계약 위반으로 떨어지기 때문이다. 뷰는 두 칸을
다 내므로 그 이유가 여기에는 해당하지 않는다. 태워야 하는 이유는 도메인 허용 목록이다 —
목록 밖 값이 장부에 들어오면 `keywords_domain` 이 정제 단계에서 `ValueError` 를 올려 배치가
통째로 죽는다. 판별을 태우면 그 행만 DLQ 로 간다 (S15P21A102-247 코드리뷰).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.ingest import backfill
from trendin.spark.io import jdbc
from trendin.spark.io.contract import KNOWN_SCHEMA_VERSION
from trendin.spark.io.schema import CORRUPT_FIELD

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# 생산자가 소유하는 창구. 정의는 `common/collect/ledger.py` 의 DDL 에 있다.
VIEW = "collected_article_event"

# 없으면 예외 대신 NULL 을 준다 (`io/contents.py` 와 같은 방식).
EXISTS_SQL = f"SELECT to_regclass('{VIEW}') IS NOT NULL"

# 뷰의 칸 이름이 곧 봉투의 필드 이름이다. 여기서 별칭을 붙이지 않는 것이 요점이다 —
# 이름을 맞추는 자리가 뷰 한 곳뿐이어야 어긋났을 때 볼 데가 하나다.
VIEW_COLUMNS = (
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
    "paywalled",
    "source_country",
)

SELECT_SQL = f"""
SELECT {", ".join(VIEW_COLUMNS)}
  FROM {VIEW}
 WHERE collected_at_ts >= %s
 ORDER BY collected_at_ts, source_id, article_id
"""

# 소스 → 국가. **거울 표를 직접 읽는다.**
#
# 처음에는 뷰에서 `DISTINCT` 로 뽑았는데 **장부에 기사가 있는 소스만 나온다.** 2026-09-18
# 로컬에서 목록 소스 둘(`cosmopolitan` · `harpersbazaar`)이 그렇게 빠졌다 — 거울에는 `KR` 로
# 있는데 장부에 그 소스의 행이 없어서, 백필로 되읽은 기사 39건이 전부 `XX` 가 됐다.
#
# 그래서 이 한 자리에서는 뷰가 아니라 거울 표를 본다. 이 모듈이 `collected_article` 을 직접
# 읽지 않는 이유는 **칸이 자주 바뀌는 큰 표**라 뷰 한 겹이 그 변화를 흡수해야 하기 때문인데,
# 거울은 그 사정이 없다 — 칸이 `(source, country)` 둘뿐이고 존재 목적이 "SQL 안에서 읽히는
# 것" 이다 (`common/collect/ledger.py` 의 DDL 주석). 뷰 자신도 이 표를 JOIN 해서 읽는다.
#
# 진실의 자리는 여전히 코드의 `SourceDef.country` 이고, 수집 DAG 의 `ensure_schema` 가 매
# 실행 거울을 그 값으로 UPSERT 한다.
SOURCE_COUNTRY_TABLE = "collect_source_country"
SOURCE_COUNTRY_EXISTS_SQL = f"SELECT to_regclass('{SOURCE_COUNTRY_TABLE}') IS NOT NULL"
SOURCE_COUNTRY_SQL = f"SELECT source, country FROM {SOURCE_COUNTRY_TABLE}"


def lookback(config: Config) -> timedelta:
    """창의 길이. **기본값을 코드에 두지 않는다** (S15P21A102-247 코드리뷰).

    `conf/base.yaml` 이 값을 든다. 여기 숫자를 하나 더 두면 두 곳이 같은 것을 말하게 되고,
    한쪽만 고쳐졌을 때 어느 쪽이 이겼는지 읽는 사람이 알 수 없다.
    """
    hours = int(config.require("ingest.ledger.lookback_hours"))
    if hours <= 0:
        raise ConfigError(f"ingest.ledger.lookback_hours 는 양수여야 한다: {hours}")
    return timedelta(hours=hours)


def view_ready(config: Config) -> bool:
    """창구가 실제로 있는지.

    **없으면 만들지 않는다.** 뷰는 생산자 소유이고 그쪽 DAG 의 첫 태스크가 만든다. 소비
    측이 만들면 정의를 둘이 나눠 갖게 되고, 한쪽만 고쳐졌을 때 조용히 갈린다.
    """
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(EXISTS_SQL)
        row = cur.fetchone()
    return bool(row and row[0])


def source_countries(config: Config) -> dict[str, str]:
    """소스 → 국가 지도. 객체만 되읽는 백필 경로(모드 B)가 국가를 채우는 데 쓴다.

    **등록된 소스 전부를 낸다.** 기사가 한 건도 없는 소스도 들어 있다 — 그게 뷰가 아니라
    거울 표를 읽는 이유다 (`SOURCE_COUNTRY_SQL` 의 주석).

    표가 없으면 빈 지도다. 백필은 수집 스키마 없이도 도는 경로이므로 여기서 죽이지 않는다.
    국가는 `XX` 로 남고, 그 상태는 통계의 구멍으로 숨지 않는다 — 국가 칸이 `XX` 인 것이
    화면에서 곧 보인다.
    """
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(SOURCE_COUNTRY_EXISTS_SQL)
        row = cur.fetchone()
        if not (row and row[0]):
            log.warning("%s 표가 없다 — 백필 봉투의 국가를 비운다 (XX)", SOURCE_COUNTRY_TABLE)
            return {}
        cur.execute(SOURCE_COUNTRY_SQL)
        return {str(source): str(country) for source, country in cur.fetchall()}


def list_events(config: Config, *, since: datetime) -> list[dict[str, Any]]:
    """창 안의 행을 봉투로. 뷰가 없으면 여기서 죽는다.

    **조용히 0건으로 끝나지 않는 것이 중요하다.** 뷰가 없는 DB 에서 빈 목록을 주면
    "수집이 0건이었다" 와 구분되지 않고, 그 차이는 며칠 뒤 통계의 구멍으로만 드러난다.
    """
    if not view_ready(config):
        raise ConfigError(
            f"{VIEW} 뷰가 없다 — 수집 DAG 의 스키마 태스크가 아직 안 돌았거나 "
            f"다른 DB 를 보고 있다 (S15P21A102-247)"
        )

    bucket = backfill.raw_bucket(config)
    with jdbc.connection(config) as conn, conn.cursor() as cur:
        cur.execute(SELECT_SQL, (since,))
        rows = cur.fetchall()
    return [_envelope(dict(zip(VIEW_COLUMNS, row)), bucket=bucket) for row in rows]


def _envelope(row: dict[str, Any], *, bucket: str) -> dict[str, Any]:
    """뷰 한 행 → 봉투 하나. 뷰에 없는 칸은 상수이거나 `None` 이다.

    `run_id` 가 `None` 인 이유는 발급이라는 단계가 없어졌기 때문이다. 값의 뜻이 "이 기사를
    발급한 수집 실행" 이었는데 이제 그런 실행이 없다. 지어내는 대신 비운다 — 모드 B 가
    같은 이유로 같은 선택을 했다 (`backfill._envelope`).
    """
    return {
        **{name: row[name] for name in VIEW_COLUMNS},
        "schema_version": KNOWN_SCHEMA_VERSION,
        "bucket": bucket,
        "run_id": None,
        "status": backfill.SYNTHETIC_STATUS,
        "record_count": backfill.SYNTHETIC_RECORD_COUNT,
        # 장부가 객체 크기를 들고 있지 않다. 크기 대조 검증은 원래도 없었다.
        "size_bytes": None,
        "format": backfill.SYNTHETIC_FORMAT,
        "compression": backfill.SYNTHETIC_COMPRESSION,
        "failure_reason": None,
        CORRUPT_FIELD: None,
    }


def read_events(spark: Any, config: Config, *, now: datetime | None = None) -> "DataFrame":
    """창 안의 봉투를 **판별 전** 프레임으로. 칸과 타입이 Kafka 시절 `parse_events` 와 같다.

    조립을 `backfill.envelope_frame` 에 맡긴다. 두 경로가 같은 함수를 쓰면 칸이 어긋날
    자리가 없다.

    **판별 칸을 붙이지 않는다.** 부른 쪽이 `with_decision` 으로 `classify` 를 태운다 —
    백필과 갈리는 자리가 여기다 (S15P21A102-247 코드리뷰).
    """
    window = lookback(config)
    since = (now or datetime.now(timezone.utc)) - window
    envelopes = list_events(config, since=since)
    log.info(
        "장부 읽기: view=%s since=%s(%s시간) 봉투=%d",
        VIEW,
        since.isoformat(),
        int(window.total_seconds() // 3600),
        len(envelopes),
    )
    return backfill.envelope_frame(spark, envelopes)
