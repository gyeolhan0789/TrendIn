"""MinIO 객체 조회 ([02 §3]).

**`binaryFile` 소스를 쓰지 않는다.** 계약이 `OBJECT_NOT_FOUND` 를 **이벤트 하나의** DLQ
사유로 정의하는데, `binaryFile` 은 없는 경로가 하나만 섞여도 계획 단계에서
`[PATH_NOT_FOUND]` 로 **배치 전체를 죽인다.** `ignoreMissingFiles` 는 목록을 만든 뒤 파일이
사라진 경우만 덮으므로 이 상황에는 듣지 않는다 (2026-09-08 실측). 이벤트 하나가 가리키는
객체가 없다고 그 배치의 나머지 수백 건을 버릴 수는 없다.

그래서 executor 에서 행마다 S3 클라이언트로 가져온다. 부수 효과로 **바이트가 DataFrame 을
거치지 않는다** — 받아서 해싱하고 검증한 뒤 판별만 남기고 버리므로 배치가 가벼워진다.

S3A 설정(`common/session.py`)은 그대로 둔다. `curated` 쓰기가 그 경로를 쓴다 ([01 §3]).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trendin.spark.common.config import Config
from trendin.spark.common.logging import get_logger

log = get_logger(__name__)

DEFAULT_REGION = "us-east-1"

# 객체가 없을 때 S3 가 주는 코드. MinIO 도 같은 값을 쓴다.
_NOT_FOUND = {"404", "NoSuchKey", "NoSuchBucket"}


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


def fetch(store: StoreConfig, bucket: str, key: str) -> bytes | None:
    """객체 바이트. 없으면 `None`.

    **없는 것과 못 읽는 것을 가른다.** 404 만 `None` 이고 나머지는 그대로 올린다. 403 을
    "없음" 으로 무시하면 정책이 잘못 붙은 날 배치가 통째로 `OBJECT_NOT_FOUND` DLQ 가 되고,
    그건 생산자 잘못으로 보인다 — 우리 키 설정이 틀린 것인데.
    """
    from botocore.exceptions import ClientError

    try:
        return client(store).get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as exc:
        error = exc.response.get("Error", {})
        status = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
        if status in _NOT_FOUND or str(error.get("Code", "")) in _NOT_FOUND:
            return None
        raise
