"""객체 검증 단계 ([02 §3]). 기사 이벤트만 탄다.

메시지 판별을 통과한 기사 이벤트에 대해 세 가지를 본다:

1. `object_key` 가 가리키는 객체가 있는가 — 없으면 `OBJECT_NOT_FOUND`
   (**키만** 해당한다. 버킷이 없으면 `io/objects.fetch` 가 `BucketNotFound` 로 올려 배치를
   멈춘다 — 이벤트 하나의 문제가 아니라 저장소를 잘못 보고 있다는 뜻이라서다)
2. **받은 바이트**의 sha256 이 메시지의 `checksum` 과 같은가 — 아니면 `CHECKSUM_MISMATCH`
3. `article.json` 이 필수 필드를 갖췄고 이벤트와 같은 기사를 가리키는가 —
   아니면 `ARTICLE_CONTRACT_VIOLATION`

**해싱 대상은 받은 바이트다.** 파싱한 뒤 다시 직렬화해서 해싱하면 키 순서·공백·유니코드
이스케이프가 달라져 전량 불일치한다 (`contract.verify_checksum` 이 그 이유를 들고 있고
`test_재직렬화한_바이트로_해싱하면_불일치한다` 가 고정한다).

**3 번이 필요한 이유** — checksum 은 "내용이 온전한가" 에만 답한다. 이벤트가 엉뚱한
(그러나 온전한) 객체를 가리키면 체크섬은 통과하고 도메인·소스가 어긋난 문서가 들어온다.
그 오염은 몇 주 뒤에 발견된다.

**통과한 객체의 `article.json` 텍스트를 함께 내보낸다.** 170 에서는 검증만 하고 바이트를
버렸는데, 정제([03])가 그 내용을 필요로 하면서 선택지가 둘이 됐다 — 정제 단계에서 다시
조회하거나, 여기서 한 번 읽은 것을 실어 보내는 것.

후자를 고른 이유는 둘이다. **조회가 이 단계에서 가장 비싼 일이고**(그래서 처리 이력 대조가
조회보다 먼저다, `ingest/batch`), 두 번 읽으면 그 사이에 객체가 바뀔 수 있어 **검증한 것과
정제한 것이 다른 바이트가 된다.** checksum 을 대조해 둔 의미가 없어진다.

대가는 배치 무게다. 원시 바이트가 아니라 디코드된 텍스트만 싣고(해싱은 이미 끝났다)
[00 §3] 규모에서 기사 하나가 수 KB 라 감당된다.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, Mapping

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger
from trendin.spark.io import objects as store_io
from trendin.spark.io.contract import ErrorType, check_article, verify_checksum

if TYPE_CHECKING:
    from pyspark.sql import DataFrame

log = get_logger(__name__)

# `(error_type, detail, article_json)`. 통과면 앞 둘이 `None` · 빈 문자열이고 셋째에
# `article.json` 텍스트가 있다. 실패면 셋째가 `None` 이다 — 검증을 통과하지 못한 내용을
# 하류로 흘리지 않는다.
Outcome = tuple[str | None, str, str | None]
Fetch = Callable[[str, str], bytes | None]

# 검증에 실패한 경우의 앞 두 칸 뒤에 붙는 값.
_NO_ARTICLE: str | None = None

# 통과할 때 쓰는 자리표시. 실제 텍스트는 `verify` 가 채운다.
ARTICLE_JSON = "article_json"


def verify(
    fetch: Fetch, event: Mapping[str, Any], *, require_checksum: bool = True
) -> Outcome:
    """기사 이벤트 하나. `fetch(bucket, key)` 를 주입받아 저장소 없이도 검사할 수 있다.

    순서가 의미를 갖는다 — 존재 → checksum → 내용. 뒤집으면 없는 객체를 "체크섬 불일치"
    로 보고하게 되고, 생산자가 저장이 아니라 해시를 의심한다.

    **`require_checksum=False` 는 백필 전용이다** ([02 §6] 모드 B). 메시지가 없으니 이벤트의
    `checksum` 도 없고, 대신 객체 메타데이터의 `content-sha256` 을 쓴다. 그 규약이 확정되기
    전에 올라간 객체에는 그 값이 없는데, **없는 값을 실패로 처리하면 옛 객체를 재처리에서
    통째로 버린다.** 그쪽이 검증을 건너뛰는 것보다 나쁘다고 규격이 정했다. 건너뛴 건수는
    부른 쪽(`ingest/backfill.py`)이 목록 조회 시점에 이미 알고 있어 [03 §7] 에 센다.

    평시 경로(`--source ledger`)에서는 기본값 `True` 다 — 봉투의 `checksum` 이 없으면
    `io/contract._check_article` 이 이미 메시지 단계에서 거절한다.
    """
    bucket = event.get("bucket")
    key = event.get("object_key")
    data = fetch(str(bucket), str(key))
    if data is None:
        return (
            ErrorType.OBJECT_NOT_FOUND.value,
            f"객체가 없다: s3://{bucket}/{key}",
            _NO_ARTICLE,
        )

    checksum = event.get("checksum")
    skip_checksum = not require_checksum and (
        checksum is None or (isinstance(checksum, str) and not checksum.strip())
    )
    if not skip_checksum:
        verdict = verify_checksum(checksum, data)
        if verdict is not None:
            assert verdict.error_type is not None  # noqa: S101 — Verdict 의 불변식
            return verdict.error_type.value, verdict.detail, _NO_ARTICLE

    try:
        text = data.decode("utf-8")
        article = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # checksum 은 통과했는데 JSON 이 아니다 — 생산자가 그 바이트를 그대로 저장했다는 뜻.
        return (
            ErrorType.ARTICLE_CONTRACT_VIOLATION.value,
            f"article.json 을 파싱하지 못했다: {exc}",
            _NO_ARTICLE,
        )
    if not isinstance(article, Mapping):
        return (
            ErrorType.ARTICLE_CONTRACT_VIOLATION.value,
            f"article.json 이 객체가 아니다: {type(article).__name__}",
            _NO_ARTICLE,
        )

    verdict = check_article(article, event)
    if verdict is not None:
        assert verdict.error_type is not None  # noqa: S101
        return verdict.error_type.value, verdict.detail, _NO_ARTICLE
    # 파싱한 것을 다시 직렬화하지 않고 **받은 텍스트 그대로** 넘긴다. 다시 만들면 키 순서와
    # 유니코드 이스케이프가 달라져, 나중에 이 값으로 checksum 을 되짚을 수 없다.
    return None, "", text


def _outcome_schema():
    from pyspark.sql.types import StringType, StructField, StructType

    return StructType(
        [
            StructField("error_type", StringType(), True),
            StructField("detail", StringType(), True),
            StructField(ARTICLE_JSON, StringType(), True),
        ]
    )


def _verify_udf(store: store_io.StoreConfig, *, require_checksum: bool = True):
    """행마다 `verify()` 를 부른다.

    `StoreConfig` 는 closure 로 실려 간다 — 문자열 넷이라 직렬화가 가볍다. 클라이언트는
    executor 프로세스당 하나로 재사용된다 (`io/objects.client`).
    """
    from pyspark.sql import functions as F

    def _apply(row):
        def fetch(bucket: str, key: str) -> bytes | None:
            return store_io.fetch(store, bucket, key)

        return verify(fetch, row.asDict(), require_checksum=require_checksum)

    return F.udf(_apply, _outcome_schema())


def verifier(
    config: Config, *, columns: tuple[str, ...], require_checksum: bool = True
) -> Callable[["DataFrame"], "DataFrame"]:
    """설정에서 검증 함수를 만든다. `process_batch` 에 주입한다.

    함수를 돌려주는 이유는 배치 처리에서 저장소를 떼어내기 위해서다 — 층 2 테스트가 가짜를
    끼워 넣어 MinIO 없이 라우팅을 검사한다 ([09 §4]).
    """
    store = store_io.store_config(config)

    def _verify_frame(articles: "DataFrame") -> "DataFrame":
        from pyspark.sql import functions as F

        envelope = F.struct(*[F.col(name) for name in columns])
        judged = articles.withColumn(
            "_outcome", _verify_udf(store, require_checksum=require_checksum)(envelope)
        )
        return (
            judged.withColumn("error_type", F.col("_outcome.error_type"))
            .withColumn("detail", F.coalesce(F.col("_outcome.detail"), F.lit("")))
            .withColumn(ARTICLE_JSON, F.col(f"_outcome.{ARTICLE_JSON}"))
            .drop("_outcome")
        )

    return _verify_frame
