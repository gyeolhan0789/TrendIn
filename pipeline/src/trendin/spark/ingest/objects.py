"""객체 검증 단계 ([02 §3]). 기사 이벤트만 탄다.

메시지 판별을 통과한 기사 이벤트에 대해 세 가지를 본다:

1. `object_key` 가 가리키는 객체가 있는가 — 없으면 `OBJECT_NOT_FOUND`
2. **받은 바이트**의 sha256 이 메시지의 `checksum` 과 같은가 — 아니면 `CHECKSUM_MISMATCH`
3. `article.json` 이 필수 필드를 갖췄고 이벤트와 같은 기사를 가리키는가 —
   아니면 `ARTICLE_CONTRACT_VIOLATION`

**해싱 대상은 받은 바이트다.** 파싱한 뒤 다시 직렬화해서 해싱하면 키 순서·공백·유니코드
이스케이프가 달라져 전량 불일치한다 (`contract.verify_checksum` 이 그 이유를 들고 있고
`test_재직렬화한_바이트로_해싱하면_불일치한다` 가 고정한다).

**3 번이 필요한 이유** — checksum 은 "내용이 온전한가" 에만 답한다. 이벤트가 엉뚱한
(그러나 온전한) 객체를 가리키면 체크섬은 통과하고 도메인·소스가 어긋난 문서가 들어온다.
그 오염은 몇 주 뒤에 발견된다.
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

# `(error_type, detail)`. 통과면 둘 다 `None` · 빈 문자열이다.
Outcome = tuple[str | None, str]
Fetch = Callable[[str, str], bytes | None]

_PASS: Outcome = (None, "")


def verify(fetch: Fetch, event: Mapping[str, Any]) -> Outcome:
    """기사 이벤트 하나. `fetch(bucket, key)` 를 주입받아 저장소 없이도 검사할 수 있다.

    순서가 의미를 갖는다 — 존재 → checksum → 내용. 뒤집으면 없는 객체를 "체크섬 불일치"
    로 보고하게 되고, 생산자가 저장이 아니라 해시를 의심한다.
    """
    bucket = event.get("bucket")
    key = event.get("object_key")
    data = fetch(str(bucket), str(key))
    if data is None:
        return (
            ErrorType.OBJECT_NOT_FOUND.value,
            f"객체가 없다: s3://{bucket}/{key}",
        )

    verdict = verify_checksum(event.get("checksum"), data)
    if verdict is not None:
        assert verdict.error_type is not None  # noqa: S101 — Verdict 의 불변식
        return verdict.error_type.value, verdict.detail

    try:
        article = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # checksum 은 통과했는데 JSON 이 아니다 — 생산자가 그 바이트를 그대로 저장했다는 뜻.
        return (
            ErrorType.ARTICLE_CONTRACT_VIOLATION.value,
            f"article.json 을 파싱하지 못했다: {exc}",
        )
    if not isinstance(article, Mapping):
        return (
            ErrorType.ARTICLE_CONTRACT_VIOLATION.value,
            f"article.json 이 객체가 아니다: {type(article).__name__}",
        )

    verdict = check_article(article, event)
    if verdict is not None:
        assert verdict.error_type is not None  # noqa: S101
        return verdict.error_type.value, verdict.detail
    return _PASS


def _outcome_schema():
    from pyspark.sql.types import StringType, StructField, StructType

    return StructType(
        [
            StructField("error_type", StringType(), True),
            StructField("detail", StringType(), True),
        ]
    )


def _verify_udf(store: store_io.StoreConfig):
    """행마다 `verify()` 를 부른다.

    `StoreConfig` 는 closure 로 실려 간다 — 문자열 넷이라 직렬화가 가볍다. 클라이언트는
    executor 프로세스당 하나로 재사용된다 (`io/objects.client`).
    """
    from pyspark.sql import functions as F

    def _apply(row):
        def fetch(bucket: str, key: str) -> bytes | None:
            return store_io.fetch(store, bucket, key)

        return verify(fetch, row.asDict())

    return F.udf(_apply, _outcome_schema())


def verifier(config: Config, *, columns: tuple[str, ...]) -> Callable[["DataFrame"], "DataFrame"]:
    """설정에서 검증 함수를 만든다. `process_batch` 에 주입한다.

    함수를 돌려주는 이유는 배치 처리에서 저장소를 떼어내기 위해서다 — 층 2 테스트가 가짜를
    끼워 넣어 MinIO 없이 라우팅을 검사한다 ([09 §4]).
    """
    store = store_io.store_config(config)

    def _verify_frame(articles: "DataFrame") -> "DataFrame":
        from pyspark.sql import functions as F

        envelope = F.struct(*[F.col(name) for name in columns])
        judged = articles.withColumn("_outcome", _verify_udf(store)(envelope))
        return (
            judged.withColumn("error_type", F.col("_outcome.error_type"))
            .withColumn("detail", F.coalesce(F.col("_outcome.detail"), F.lit("")))
            .drop("_outcome")
        )

    return _verify_frame
