"""`--source objects` — Kafka 없이 MinIO 프리픽스를 훑어 재처리한다 ([02 §6] 모드 B).

**왜 따로 필요한가** — `Trigger.AvailableNow` 는 오프셋을 진행시키므로, 이미 소비한 이벤트는
Kafka 를 다시 읽어도 오지 않는다. checkpoint 를 지우는 방법은 쓰지 않는다: 토픽의 모든
이벤트를 처음부터 다시 읽게 되고 범위를 지정할 수 없다.

**이 모드가 성립하는 근거** — 불변식 5 가 "이벤트는 MinIO 에 raw·article.json 이 있음을
`stat` 으로 확인한 뒤에만 낸다" 를 보장하므로, **객체가 있는 것은 곧 이벤트가 나갔던 것**이다.
그리고 `article.json` 은 자기 완결적이라(불변식 9 가 필수 필드를 보장) 메시지를 재구성하는 데
다른 파일이 필요하지 않다.

```
spark-submit ingest.py --source objects --domain fashion \\
  --from 2026-09-01 --to 2026-09-03 --force
```

**`--from`·`--to` 는 발행일이다** — 키의 날짜가 발행일이기 때문이다 (불변식 10,
`collect/keys.py`). 수집일로 훑고 발행일로 다시 거르던 배치 계약 시절보다 오히려 정확하다.

### 봉투 계약 검증을 건너뛴다

재구성한 봉투에는 `url`·`title`·`published_at` 이 없다 — 그 값들은 `article.json` 안에 있고,
[02 §6] 이 "나머지 필드는 article.json 안에 있다" 로 그렇게 정했다. 그래서 `io/contract.classify`
를 부르지 않는다. 불렀다면 **재구성한 모든 이벤트가 `CONTRACT_VIOLATION` 으로 DLQ 에 간다** —
검증하는 대상이 우리가 방금 만든 봉투이므로 그 검증에 뜻이 없다.

대신 진짜 검증은 그대로 남는다:

| 무엇 | 어디서 |
| --- | --- |
| 객체가 있는가 | 목록 조회 자체 (없으면 목록에 없다) |
| 바이트가 온전한가 | 객체 메타데이터 `content-sha256` 대조 ([02 §6]) |
| 필수 필드가 있는가 | `io/contract.check_article` — 봉투가 아니라 객체를 본다 |
| 아는 도메인인가 | 아래 `build_request` 가 허용 목록으로 막는다 |

### 요약 이벤트는 복구할 수 없다

객체가 없으므로 흔적이 MinIO 에 남지 않는다. 즉 이 모드로는 [02 §4] 의 수집 상태를 복구할
수 없고 **문서만 복구된다.** 생산자 수집 이력을 읽는 대안은 쓰지 않는다 — 담당 1 소유의 앱 DB
테이블을 소비 측이 직접 읽는 결합이 생기고, 컬럼이 하나 바뀌면 이쪽이 조용히 깨진다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Iterator

from trendin.spark.common.config import Config, ConfigError
from trendin.spark.common.logging import get_logger
from trendin.spark.ingest.routing import COMPLETED, STAGE_NORMALIZE
from trendin.spark.io import objects as store_io
from trendin.spark.io.contract import DOMAIN_VALUES, KNOWN_SCHEMA_VERSION
from trendin.spark.io.schema import CORRUPT_FIELD, EVENT_SCHEMA, META_COLUMNS

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

ARTICLE_OBJECT = "article.json"
DEFAULT_RAW_BUCKET = "raw-data"

# 재구성한 봉투가 늘 갖는 값. `status` 가 `success` 인 이유는 객체가 있다는 것이 곧 저장
# 확인이 끝났다는 뜻이기 때문이다 (불변식 5). `record_count` 는 기사 이벤트라 늘 1 이다.
SYNTHETIC_STATUS = "success"
SYNTHETIC_RECORD_COUNT = 1
# `format` 은 판별자로 쓰인다 (`web-collect.md` 필드 규약). 기사 객체는 늘 json 이다.
SYNTHETIC_FORMAT = "json"
SYNTHETIC_COMPRESSION = "none"


@dataclass(frozen=True, slots=True)
class BackfillRequest:
    """훑을 범위. `--domain`·`--from`·`--to` 가 그대로 들어온다."""

    domain: str
    date_from: date
    date_to: date

    def days(self) -> Iterator[date]:
        """`date_to` 를 **포함**한다 ([02 §6] 의 `--to` 설명)."""
        current = self.date_from
        while current <= self.date_to:
            yield current
            current += timedelta(days=1)


@dataclass(frozen=True, slots=True)
class BackfillStats:
    """목록 조회에서 이미 알 수 있는 것 ([03 §7]).

    **checksum 을 건너뛴 건수를 여기서 센다.** 메타데이터가 있는지는 `head_object` 로 이미
    알았으므로, 검증 단계까지 들고 갈 이유가 없다.
    """

    listed: int = 0
    checksum_missing: int = 0


def parse_day(raw: str | None, *, flag: str) -> date:
    """`YYYY-MM-DD`. 없거나 형태가 아니면 죽는다.

    **여기서 죽는 것이 맞다.** 범위가 틀린 백필은 아무것도 안 하거나 엉뚱한 구간을 다시
    처리하고, 둘 다 조용하다.
    """
    if not raw:
        raise ConfigError(f"--source objects 에는 {flag} 가 필요하다 ([02 §6])")
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise ConfigError(f"{flag} 가 YYYY-MM-DD 형태가 아니다: {raw!r}") from None


def build_request(
    domain: str | None, date_from: str | None, date_to: str | None
) -> BackfillRequest:
    """CLI 인자에서. 허용 목록 밖 도메인은 여기서 막는다."""
    # 공백만 있는 값을 먼저 다듬는다. `if not domain` 만 보면 `--domain "  "` 이 아래
    # 허용 목록 검사로 내려가서 "허용 목록에 없는 domain: '   '" 로 보고된다 — 사람이
    # 오타를 찾는 대신 목록을 들여다보게 된다.
    slug = (domain or "").strip().lower()
    if not slug:
        raise ConfigError("--source objects 에는 --domain 이 필요하다 ([02 §6])")
    if slug not in DOMAIN_VALUES:
        # `io/contract.DOMAIN_VALUES` 가 유일한 방어선이다 ([01 §6]). 모드 B 는 `classify`
        # 를 타지 않으므로 그 방어를 여기서 한 번 더 세운다.
        raise ConfigError(f"허용 목록에 없는 domain: {domain!r} (허용: {sorted(DOMAIN_VALUES)})")

    start = parse_day(date_from, flag="--from")
    end = parse_day(date_to, flag="--to")
    if end < start:
        raise ConfigError(f"--from 이 --to 보다 늦다: {start} > {end}")
    return BackfillRequest(domain=slug, date_from=start, date_to=end)


def raw_bucket(config: Config) -> str:
    return str(config.get("minio.buckets.raw", DEFAULT_RAW_BUCKET) or DEFAULT_RAW_BUCKET)


def parse_key(key: str) -> tuple[str, str, str, str] | None:
    """`{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/{article_id}/article.json` 을 뜯는다.

    `(domain, source, route, article_id)`. 형태가 아니면 `None` — 버킷에 다른 규칙으로 올라간
    객체가 섞여 있어도 백필이 죽지 않는다.
    """
    parts = key.split("/")
    if len(parts) != 8 or parts[-1] != ARTICLE_OBJECT:
        return None
    domain, source, route, _year, _month, _day, article_id = parts[:7]
    if not all((domain, source, route, article_id)):
        return None
    return domain, source, route, article_id


def list_articles(
    store: store_io.StoreConfig, bucket: str, request: BackfillRequest
) -> tuple[list[dict[str, Any]], BackfillStats]:
    """범위 안의 `article.json` 을 훑어 봉투를 재구성한다.

    **프리픽스를 세 단계로 좁힌다** — 도메인 아래의 소스, 소스 아래의 `route`, 그리고 그 아래
    날짜다. 키의 날짜가 소스·route 뒤에 오기 때문에(`collect/keys.py`) 날짜만으로는 프리픽스를
    만들 수 없다. 그렇다고 도메인 전체를 나열하면 보관 기간 90일치가 전부 올라온다.

    **`head_object` 를 객체마다 한 번 부른다.** checksum 이 메타데이터에 있고([02 §6]) 그것
    없이는 손상 검출이 성립하지 않는다. 목록 하나에 요청 하나가 더 붙지만, 백필은 평시 경로가
    아니라 사람이 범위를 정해 부르는 것이라 이 비용을 받는다.
    """
    envelopes: list[dict[str, Any]] = []
    listed = 0
    missing = 0

    for source_prefix in store_io.list_prefixes(store, bucket, f"{request.domain}/"):
        for route_prefix in store_io.list_prefixes(store, bucket, source_prefix):
            for day in request.days():
                prefix = f"{route_prefix}{day:%Y/%m/%d}/"
                for key in store_io.list_keys(store, bucket, prefix):
                    parsed = parse_key(key)
                    if parsed is None:
                        continue
                    listed += 1
                    metadata = store_io.head_metadata(store, bucket, key)
                    if metadata is None:
                        # 목록에는 있었는데 지금 없다. 보관 기간이 그 사이에 지났다.
                        log.warning("목록 뒤 사라진 객체를 건너뛴다: %s", key)
                        continue
                    checksum = metadata.get(store_io.META_CHECKSUM)
                    if not checksum:
                        missing += 1
                    envelopes.append(
                        _envelope(
                            bucket,
                            key,
                            parsed,
                            checksum=checksum,
                            collected_at=metadata.get(store_io.META_COLLECTED_AT),
                        )
                    )

    stats = BackfillStats(listed=listed, checksum_missing=missing)
    log.info(
        "백필 목록: domain=%s %s~%s 객체=%d checksum 없음=%d",
        request.domain,
        request.date_from,
        request.date_to,
        stats.listed,
        stats.checksum_missing,
    )
    return envelopes, stats


def _envelope(
    bucket: str,
    key: str,
    parsed: tuple[str, str, str, str],
    *,
    checksum: str | None,
    collected_at: str | None,
) -> dict[str, Any]:
    """봉투 한 개. 없는 칸은 `None` 으로 둔다 — 객체 안에 있다 ([02 §6])."""
    domain, source, _route, article_id = parsed
    return {
        # 규칙은 계약과 같다 ([08 §3] 의 `event_id` 꼴 표).
        "event_id": f"{source}-{article_id}",
        "schema_version": KNOWN_SCHEMA_VERSION,
        "bucket": bucket,
        "object_key": key,
        # 우리는 raw 를 읽지 않으므로 재구성하지 않는다.
        "raw_object_key": None,
        "domain": domain,
        "source_id": source,
        "article_id": article_id,
        # 기사는 실행에 속하지 않는다 ([02 §2]).
        "run_id": None,
        "url": None,
        "title": None,
        "published_at": None,
        "collected_at": collected_at,
        "status": SYNTHETIC_STATUS,
        "record_count": SYNTHETIC_RECORD_COUNT,
        "size_bytes": None,
        "checksum": checksum,
        "format": SYNTHETIC_FORMAT,
        "compression": SYNTHETIC_COMPRESSION,
        "failure_reason": None,
        "members_only": None,
        CORRUPT_FIELD: None,
    }


# 재구성한 봉투 프레임의 칸. 평시 경로(`ingest/collected.py`)와 같은 형태여야 한다 —
# 그 뒤로는 두 경로가 완전히 같은 코드다 ([02 §6] 4번).
_FRAME_SCHEMA_FIELDS = tuple(field.name for field in EVENT_SCHEMA.fields)


def envelope_frame(spark, envelopes: list[dict[str, Any]]) -> "DataFrame":
    """봉투 목록을 판별 **전** 프레임으로. 칸과 타입이 Kafka 시절 `parse_events` 와 같다.

    판별 칸을 붙이지 않는 것이 요점이다. 붙일지 말지는 부른 쪽이 정한다 — 평시 경로
    (`ingest/collected.py`)는 `classify` 를 태워야 하고 백필은 태우면 안 되는데, 그 차이가
    여기 섞여 있으면 한쪽을 고칠 때 다른 쪽이 딸려 온다.

    Kafka 메타 칸(`partition`·`offset`)은 `null`·`-1` 이다. 그 값이 뜻을 갖지 않는 경로라
    처리 이력에도 그렇게 남는 것이 맞다 — 0 을 넣으면 진짜 0번 파티션의 이벤트와 섞인다.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    schema = StructType(
        [
            StructField("message_key", StringType(), True),
            # Kafka 시절부터 쓰던 타입을 그대로 둔다. 값은 `null` 이지만
            # 타입이 갈리면 두 경로를 같은 코드로 다룰 수 없게 된다.
            StructField("partition", IntegerType(), True),
            StructField("offset", LongType(), True),
            StructField("kafka_timestamp", TimestampType(), True),
            StructField("raw_value", StringType(), True),
            *EVENT_SCHEMA.fields,
        ]
    )
    rows = [
        {
            "message_key": envelope["source_id"],
            "partition": None,
            # 처리 이력의 `topic_offset` 이 bigint 라 값이 있어야 한다. -1 은 "Kafka 에서
            # 온 것이 아니다" 를 뜻하는 자리다.
            "offset": -1,
            "kafka_timestamp": None,
            # 원본 메시지가 없다. DLQ 가 이 칸을 그대로 남기므로(`dlq_rows`) 사람이 볼 때
            # 무엇을 보고 있는지 알 수 있게 객체 키를 적는다.
            "raw_value": f"s3://{envelope['bucket']}/{envelope['object_key']}",
            **{name: envelope.get(name) for name in _FRAME_SCHEMA_FIELDS},
        }
        for envelope in envelopes
    ]
    frame = spark.createDataFrame(rows, schema)
    return frame.select(
        *META_COLUMNS,
        *[F.col(name) for name in _FRAME_SCHEMA_FIELDS if name != CORRUPT_FIELD],
        F.col(CORRUPT_FIELD),
    )


def events_frame(spark, envelopes: list[dict[str, Any]]) -> "DataFrame":
    """재구성한 봉투를 판별 칸까지 채운 프레임으로. **백필 전용이다.**

    **`with_decision` 을 타지 않는다.** 그 함수는 `classify` 로 봉투를 검증하는데, 여기서
    검증할 대상은 우리가 방금 만든 봉투다 (모듈 docstring "봉투 계약 검증을 건너뛴다").
    그래서 판별 칸을 직접 채운다 — 전부 기사 이벤트이고, 전부 `normalize` 를 목표로 한다.

    평시 경로는 이 함수를 쓰지 않는다. 그쪽 봉투는 뷰가 `url`·`published_at` 까지 내므로
    `classify` 를 통과할 수 있고, 통과시켜야 허용 목록 밖 도메인이 DLQ 로 간다
    (S15P21A102-247 코드리뷰).
    """
    from pyspark.sql import functions as F

    return envelope_frame(spark, envelopes).select(
        "*",
        F.lit("ARTICLE").alias("event_shape"),
        F.lit(None).cast("string").alias("error_type"),
        F.lit("").alias("detail"),
        F.lit(COMPLETED).alias("ledger_status"),
        F.lit(STAGE_NORMALIZE).alias("stage"),
    )
