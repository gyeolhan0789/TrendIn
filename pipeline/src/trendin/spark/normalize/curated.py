"""MinIO `curated` Parquet 쓰기 ([01 §3](../../../../spark/docs/01-architecture.md)).

```text
Bucket: curated
curated/
└─ domain=fashion/
   └─ published_date=2026-09-03/
      └─ source=vogue/
         └─ ingest_run_id=20260903T000000/
            └─ part-*.snappy.parquet
```

| 항목 | 결정 | 이유 |
| --- | --- | --- |
| 형식 | Parquet + snappy | 컬럼 프루닝. `extract` 는 몇 칸만 읽는다 |
| 파티션 | `domain`/`published_date`/`source`/`ingest_run_id` | 날짜가 앞인 이유는 [07 §3] |
| 버킷 소유 | Spark | `raw-data` 는 담당 1 소유. 섞지 않는다 |

**🚫 선행 조건 — `curated` 버킷과 Spark 쓰기 권한.** 지금 Spark 키는 `raw-data` 읽기만 한다
(`datastore/minio-init/init.sh` 의 `spark-read` 정책). 그래서 이 모듈은 **코드로는 완성이되
실제 쓰기가 확인되지 않은 상태**다 ([09 §7] 항목 4b, [10 §5] 차단 B3). 권한이 붙기 전에는
`AccessDenied` 로 죽는다 — 조용히 건너뛰지 않는 것이 맞다. 건너뛰면 `contents` 의
`body_object_key` 가 없는 파일을 가리킨다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.normalize.schema import (
    CURATED_COLUMNS,
    PARTITION_COLUMNS,
    PARTITION_SOURCE,
)

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

DEFAULT_BUCKET = "curated"
COMPRESSION = "snappy"


def curated_root(config: Config) -> str:
    """`s3a://{버킷}`. 버킷 루트부터가 [01 §3] 의 레이아웃이다.

    S3A 설정은 `common/session.py` 가 세션에 걸어 둔다 — 엔드포인트·경로 스타일·자격이
    거기 한 곳에 있고, 여기서 다시 조립하지 않는다.
    """
    bucket = str(config.get("minio.buckets.curated", DEFAULT_BUCKET) or DEFAULT_BUCKET)
    return f"s3a://{bucket}"


def curated_frame(documents: "DataFrame") -> "DataFrame":
    """Parquet 에 쓸 형태. [03 §1] 의 스물한 칸 + 파티션용 `source`.

    내부 칸(`basis`·`simhash` 등)은 여기서 떨어진다 — `curated` 는 `extract` 의 입력이고,
    필터 판정에 썼던 중간값이 그 입력에 섞이면 나중에 "이 칸은 무엇인가" 를 되짚어야 한다.
    """
    from pyspark.sql import functions as F

    return documents.select(
        *[F.col(name) for name in CURATED_COLUMNS],
        # 파티션 경로는 `source=`, 데이터 컬럼은 `source_id` 다 (`normalize/schema.py`).
        F.col("source_id").alias(PARTITION_SOURCE),
    )


def write(
    documents: "DataFrame", config: Config, *, root: str | None = None, mode: str = "overwrite"
) -> str:
    """살아남은 문서를 Parquet 으로 쓴다. 쓴 경로의 루트를 돌려준다.

    **`mode` 는 실행 안 첫 쓰기만 `overwrite` 고 그 뒤 배치는 `append` 다.** `Trigger.AvailableNow`
    는 마이크로배치를 여럿 낼 수 있는데 `ingest_run_id` 는 실행 전체에 하나다. 배치마다
    `overwrite` 하면 같은 `날짜/소스/run_id` 파티션에 배치 2 가 쓰면서 배치 1 의 문서를 지운다.
    그 판단은 `ingest/normalize.NormalizeStage` 가 들고 있다 — 여기는 모드만 받는다.

    **`mode("overwrite")` + `partitionOverwriteMode=dynamic` 이다** ([01 §4] 중복 차단 3,
    `conf/base.yaml`). 이 조합에서 덮어쓰는 것은 **이번 배치가 실제로 쓴 파티션뿐**이고,
    건드리지 않은 파티션은 남는다. `dynamic` 이 없으면 `overwrite` 가 `curated` 를 통째로
    비우므로, 그 설정이 빠진 채 이 코드가 도는 것이 이 묶음에서 가장 위험한 사고다.

    그 조합이 `--force` 재처리를 성립시킨다 — 같은 `ingest_run_id` 로 다시 돌리면 그 실행이
    쓴 파티션만 갈아치운다 ([02 §6] "재처리 시 지워야 할 것").

    **`append` 를 쓰지 않는 이유** — 재처리가 같은 문서를 파티션에 하나 더 쌓아 `extract`
    입력이 중복된다. 처리 이력이 대개 막지만 `--force` 는 그 방어를 우회한다.

    `root` 는 층 2 테스트가 임시 디렉터리를 넣는 자리다 ([09 §4]) — MinIO 를 띄우지 않고
    파티션 레이아웃과 덮어쓰기 동작을 검사한다. 운영에서는 넣지 않는다.
    """
    root = root or curated_root(config)
    frame = curated_frame(documents)
    log.info("curated 쓰기: root=%s mode=%s 파티션=%s", root, mode, "/".join(PARTITION_COLUMNS))
    (
        frame.write.mode(mode)
        .option("compression", COMPRESSION)
        .partitionBy(*PARTITION_COLUMNS)
        .parquet(root)
    )
    return root


def body_object_keys(
    spark, config: Config, documents: "DataFrame", *, root: str | None = None
) -> "DataFrame":
    """`(url_hash, body_object_key)` — 그 문서가 든 Parquet **파일**의 객체 키 ([01 §3]).

    **쓴 뒤에 되읽어 `input_file_name()` 으로 얻는다.** 쓰기 전에는 part 파일 이름을 알 수
    없다 — Spark 가 태스크 단위로 정하고, 파티션 하나에 파일이 여럿 생길 수 있다. 경로를
    파티션 디렉터리로 대신하면 [01 §3] 이 정한 "파일의 객체 키" 가 아니게 되고, 읽는 쪽이
    디렉터리를 열어 파일을 다시 찾아야 한다.

    **되읽기가 비싸지 않은 이유** — 두 칸만 읽는다. Parquet 이라 나머지 칸은 디스크에서
    올라오지 않고, [00 §3] 규모에서 이 읽기는 배치의 곁가지다.

    **한계는 규격이 이미 적어 뒀다** — 키가 파일을 가리키지 문서를 가리키지 않으므로 읽는
    쪽은 파일을 열어 `url` 로 행을 찾아야 한다. 지금은 실제 소비자가 없다 ([01 §3]).
    """
    import re

    from pyspark.sql import functions as F

    root = root or curated_root(config)
    # 이번 실행이 쓴 파티션만 읽는다. 전체를 읽으면 지난 실행분까지 훑는다.
    run_ids = [row[0] for row in documents.select("ingest_run_id").distinct().collect()]
    written = (
        spark.read.parquet(root)
        .where(F.col("ingest_run_id").isin(run_ids))
        .select("url_hash", F.input_file_name().alias("_path"))
    )
    # `s3a://버킷/키` 에서 키만 남긴다. `contents.body_object_key` 는 **버킷 안의 키**이고,
    # 버킷 이름은 설정이 들고 있다 — 키에 섞으면 버킷을 옮길 때 옛 행이 못 따라온다.
    #
    # 경로를 정규식에 넣으므로 이스케이프한다. 버킷 이름에 `.` 이 들어가는 일이 실제로
    # 있고(도메인 형태 이름), 그러면 임의의 한 글자와 맞아 키가 잘못 잘린다.
    return written.select(
        F.col("url_hash"),
        F.regexp_replace(F.col("_path"), f"^{re.escape(root)}/", "").alias("body_object_key"),
    )
