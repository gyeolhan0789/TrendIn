"""MinIO 객체 조회 ([02 §3]).

**`binaryFile` 소스를 쓰지 않는다.** 계약이 `OBJECT_NOT_FOUND` 를 **이벤트 하나의** DLQ
사유로 정의하는데, `binaryFile` 은 없는 경로가 하나만 섞여도 계획 단계에서
`[PATH_NOT_FOUND]` 로 **배치 전체를 죽인다.** `ignoreMissingFiles` 는 목록을 만든 뒤 파일이
사라진 경우만 덮으므로 이 상황에는 듣지 않는다 (2026-09-08 실측). 이벤트 하나가 가리키는
객체가 없다고 그 배치의 나머지 수백 건을 버릴 수는 없다.

그래서 executor 에서 행마다 S3 클라이언트로 가져온다. 부수 효과로 **바이트가 DataFrame 을
거치지 않는다** — 받아서 해싱하고 검증한 뒤 판별만 남기고 버리므로 배치가 가벼워진다.

S3A 설정(`common/session.py`)은 그대로 둔다. `curated` 쓰기가 그 경로를 쓴다 ([01 §3]).

**목록 조회는 드라이버에서 한다** (`list_prefixes` · `list_keys` · `head_metadata`).
`--source objects` 백필이 쓰는 경로이고([02 §6] 모드 B), 조회 결과가 곧 처리할 이벤트
목록이라 executor 로 흩어질 것이 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger

log = get_logger(__name__)

DEFAULT_REGION = "us-east-1"

# **키가** 없을 때 S3 가 주는 코드. MinIO 도 같은 값을 쓴다.
#
# `NoSuchBucket` 은 여기 없다. 버킷 부재는 `fetch` 가 `BucketNotFound` 로 올린다.
_NOT_FOUND = {"404", "NoSuchKey"}

# 버킷 자체가 없을 때의 코드. 이것도 HTTP 404 로 오므로 상태보다 **먼저** 봐야 한다 —
# 순서가 뒤집히면 위 집합의 `"404"` 가 다시 삼킨다.
_NO_SUCH_BUCKET = "NoSuchBucket"


class BucketNotFound(RuntimeError):
    """버킷 자체가 없다.

    `ConfigError` 를 쓰지 않는 이유 — 버킷 이름은 우리 설정이 아니라 **이벤트 봉투의
    `bucket` 필드**에서 온다 (`io/schema.py`). 생산자가 틀렸을 수도, 우리 `minio.endpoint`
    가 다른 MinIO 를 가리키는 것일 수도 있어서 타입으로 원인을 단정할 수 없다. 메시지에
    둘 다 적어 사람이 가른다.
    """


@dataclass(frozen=True, slots=True)
class StoreConfig:
    """executor 로 실려 가는 접속값. `Config` 를 통째로 보내지 않는 이유는 그 안에 이
    단계와 무관한 비밀(앱 DB 비밀번호)이 들어 있기 때문이다."""

    endpoint: str
    access_key: str
    secret_key: str
    region: str = DEFAULT_REGION


def store_config(config: Config) -> StoreConfig:
    return StoreConfig(
        endpoint=str(config.require("minio.endpoint")),
        access_key=str(config.require("minio.access_key")),
        secret_key=str(config.require("minio.secret_key")),
        region=str(config.get("minio.region", DEFAULT_REGION)),
    )


# executor 프로세스당 하나. 행마다 만들면 연결 수립이 조회보다 비싸진다 ([01 §5] 와 같은 이유).
_client = None
_client_key: tuple[str, str] | None = None


def client(store: StoreConfig) -> Any:
    global _client, _client_key

    key = (store.endpoint, store.access_key)
    if _client is None or _client_key != key:
        import boto3
        from botocore.config import Config as BotoConfig

        _client = boto3.client(
            "s3",
            endpoint_url=store.endpoint,
            aws_access_key_id=store.access_key,
            aws_secret_access_key=store.secret_key,
            region_name=store.region,
            # MinIO 는 가상 호스트 스타일이 아니라 경로 스타일이다 ([02 §3]).
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )
        _client_key = key
    return _client


# 메타데이터 키 (`web-collect.md` #5.1, S15P21A102-158 확정). boto3 는 `x-amz-meta-` 접두어를
# 떼고 소문자로 준다.
META_CHECKSUM = "content-sha256"
META_COLLECTED_AT = "collected-at"


def _listing(store: StoreConfig, bucket: str, prefix: str, *, delimiter: str = ""):
    """`list_objects_v2` 페이지 목록. 버킷이 없으면 `BucketNotFound`.

    **`fetch` 와 같은 규약을 지킨다** — 버킷은 인프라이므로 없으면 예외다. 백필에서 이걸
    삼키면 더 나쁘다: 목록이 비어 "그 범위에 기사가 없다" 로 보이고, `--source objects` 가
    **아무것도 하지 않은 채 정상 종료한다.** 사람이 범위를 정해 부른 복구 작업이 조용히
    빈손으로 끝나는 것이라, 복구가 안 됐다는 사실조차 남지 않는다.

    `GET` 이라 응답 본문이 있어서 `NoSuchBucket` 코드가 그대로 온다 — `head_object` 와
    다른 점이고, 그래서 버킷 검증을 이 자리에서 할 수 있다 (`head_metadata` 참조).
    """
    from botocore.exceptions import ClientError

    paginator = client(store).get_paginator("list_objects_v2")
    arguments = {"Bucket": bucket, "Prefix": prefix}
    if delimiter:
        arguments["Delimiter"] = delimiter
    try:
        # 페이지네이터는 지연 평가다. 여기서 목록으로 만들어 예외를 이 자리로 끌어온다 —
        # 안 그러면 호출부의 `for` 안에서 터져 이 함수의 규약이 뜻을 잃는다.
        return list(paginator.paginate(**arguments))
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code", "")) == _NO_SUCH_BUCKET:
            raise BucketNotFound(
                f"버킷이 없다: {bucket} (endpoint={store.endpoint}). "
                "minio.endpoint 가 맞는 MinIO 를 가리키는지, 버킷 이름이 맞는지 본다."
            ) from exc
        raise


def list_prefixes(store: StoreConfig, bucket: str, prefix: str) -> list[str]:
    """`prefix` 바로 아래의 "디렉터리" 목록. 끝에 `/` 가 붙은 채로 준다.

    `Delimiter="/"` 로 한 단계만 본다. 전체를 훑어 경로를 잘라내는 것보다 훨씬 싸다 —
    `raw-data` 는 연 25만 객체 규모라([00 §3]) 전량 나열은 백필마다 수십만 건을 받는다.

    소스와 `route` 를 이렇게 알아내는 이유는 **키의 날짜가 소스·route 뒤에 오기** 때문이다
    (`{domain}/{source}/{route}/{yyyy}/{mm}/{dd}/...`, `collect/keys.py`). 날짜로 바로
    프리픽스를 만들 수 없어서, 앞의 두 단을 먼저 알아내야 날짜까지 좁힌 프리픽스가 나온다.
    """
    found: list[str] = []
    for page in _listing(store, bucket, prefix, delimiter="/"):
        found.extend(item["Prefix"] for item in page.get("CommonPrefixes", []))
    return found


def list_keys(store: StoreConfig, bucket: str, prefix: str) -> list[str]:
    """`prefix` 아래의 객체 키 전부. 하위 디렉터리까지 내려간다.

    버킷이 없으면 `BucketNotFound` — 이유는 `_listing` 에 있다.
    """
    found: list[str] = []
    for page in _listing(store, bucket, prefix):
        found.extend(item["Key"] for item in page.get("Contents", []))
    return found


def head_metadata(store: StoreConfig, bucket: str, key: str) -> dict[str, str] | None:
    """객체의 사용자 메타데이터. 객체가 없으면 `None`, 있고 메타데이터가 없으면 빈 사전.

    **`None` 과 빈 사전을 가른다.** 없는 객체와 "메타데이터 규약이 확정되기 전에 올라간
    객체" 는 다르게 처리해야 한다 ([02 §6]) — 후자는 checksum 검증을 건너뛰고 재처리하고,
    전자는 애초에 목록에 없다.

    **⚠️ `HEAD` 는 버킷 부재와 키 부재를 가려 주지 못한다.** `HEAD` 응답에는 본문이 없어서
    S3 의 XML 에러 코드가 오지 않고, botocore 가 `Error.Code` 를 상태 코드 문자열(`"404"`)로
    채운다. 그래서 `fetch` 처럼 `NoSuchBucket` 으로 갈라낼 수 없다.

    **그래도 안전한 이유는 호출 순서다.** 이 함수를 부르는 곳은 백필뿐이고
    (`ingest/backfill.list_articles`), 그 앞에서 `list_prefixes`·`list_keys` 가 이미 같은
    버킷을 훑는다. 목록 조회는 `GET` 이라 `NoSuchBucket` 이 그대로 오므로 버킷 부재는
    **거기서** `BucketNotFound` 로 걸린다. 여기 도달했다는 것은 버킷이 있다는 뜻이고,
    남은 404 는 "목록을 만든 뒤 보관 기간이 지나 사라진 객체" 다.

    그 순서가 깨지면(목록 없이 이 함수를 먼저 부르면) 버킷 부재가 다시 키 부재로 보인다.
    b277af9 가 없앤 바로 그 경로이므로, 새 호출부를 만들 때 목록을 먼저 타는지 확인한다.
    """
    from botocore.exceptions import ClientError

    try:
        response = client(store).head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
        # 코드를 상태보다 **먼저** 본다 (`_NO_SUCH_BUCKET` 주석). `HEAD` 에서는 대개 코드가
        # `"404"` 로 오지만, 오는 경우에 삼키면 b277af9 가 없앤 경로가 되살아난다.
        if code == _NO_SUCH_BUCKET:
            raise BucketNotFound(
                f"버킷이 없다: {bucket} (endpoint={store.endpoint})"
            ) from exc
        if code in _NOT_FOUND or status in _NOT_FOUND:
            return None
        raise
    metadata = response.get("Metadata") or {}
    return {str(name).lower(): str(value) for name, value in metadata.items()}


def fetch(store: StoreConfig, bucket: str, key: str) -> bytes | None:
    """객체 바이트. **키가** 없으면 `None`. 버킷이 없으면 `BucketNotFound`.

    **없는 것과 못 읽는 것을 가른다.** 없는 키만 `None` 이고 나머지는 그대로 올린다. 403 을
    "없음" 으로 무시하면 정책이 잘못 붙은 날 배치가 통째로 `OBJECT_NOT_FOUND` DLQ 가 되고,
    그건 생산자 잘못으로 보인다 — 우리 키 설정이 틀린 것인데.

    **같은 이유가 404 에도 걸린다.** `minio.endpoint` 가 다른 MinIO 를 가리키면 붙기는 붙고
    버킷만 없어서, 그 배치의 기사 이벤트가 **전부** `NoSuchBucket` 을 맞는다. 이걸 `None` 으로
    삼키면 전량 `OBJECT_NOT_FOUND` DLQ 인데, 그 실패는 **되돌릴 수 없다** — 처리 이력에
    `stage=object` 로 적히고 (`ingest/routing.STAGE_OBJECT`) 오프셋도 전진하므로,
    endpoint 를 고쳐 재실행해도 `ledger.filter_new()` 가 걸러내 다시 읽지 않는다.
    예외로 올리면 이력·오프셋이 그대로 남아 재실행만으로 복구된다.

    **키 하나가 없는 것과는 분류가 다르다.** 키는 기사마다 다른 데이터라 하나쯤 비는 것이
    정상 경로이고, 그래서 이 모듈이 `binaryFile` 을 버리고 행마다 가져온다 (위 참조). 반면
    버킷은 인프라다 — 시스템 전체에 몇 개뿐이고 전부 알려져 있다. 없는 버킷을 가리키는
    이벤트 하나가 배치를 죽이는 편이, 조용히 비워진 배치보다 낫다.
    """
    from botocore.exceptions import ClientError

    try:
        return client(store).get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = str(error.get("Code", ""))
        status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
        # 코드를 상태보다 먼저 본다 (`_NO_SUCH_BUCKET` 주석 참조).
        if code == _NO_SUCH_BUCKET:
            raise BucketNotFound(
                f"버킷이 없다: {bucket} (endpoint={store.endpoint}). "
                "이벤트의 bucket 값이 맞는지, minio.endpoint 가 맞는 MinIO 를 가리키는지 본다."
            ) from exc
        if code in _NOT_FOUND or status in _NOT_FOUND:
            return None
        raise
