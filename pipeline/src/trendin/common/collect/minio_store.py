"""MinIO 저장 (S15P21A102-158 의 최소 구현).

S3 호환이라 boto3 를 endpoint_url 만 바꿔 쓴다. Airflow 의 S3 훅을 쓰지 않는 이유는
README 규약 12 — 태스크 함수는 Airflow 없이 테스트한다.

**삭제 경로가 없다.** 크롤러 키에 `s3:DeleteObject` 권한이 아예 없고(datastore/README.md
"키 세 벌"), 보존 기간은 코드가 아니라 버킷 수명주기 규칙(ILM)이 건다(설계 문서 #13).
"""

from __future__ import annotations

import logging

from trendin.common.collect.env import require_env

logger = logging.getLogger("trendin.collect.minio")

ENDPOINT_ENV = "TRENDIN_MINIO_ENDPOINT"
BUCKET_ENV = "TRENDIN_MINIO_BUCKET"
ACCESS_KEY_ENV = "TRENDIN_MINIO_ACCESS_KEY"
SECRET_KEY_ENV = "TRENDIN_MINIO_SECRET_KEY"


def build_client(endpoint: str, access_key: str, secret_key: str):
    """MinIO 용 S3 클라이언트. path 주소 방식이라야 버킷이 호스트명으로 안 붙는다."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        # MinIO 는 리전을 안 보지만 botocore 가 값을 요구한다.
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


class MinioObjectStore:
    """`ObjectStore` 의 실구현. 버킷 하나에 접두어로 나눈다(설계 확정 4)."""

    def __init__(self, *, bucket: str, client) -> None:
        self._bucket = bucket
        self._client = client

    @classmethod
    def from_env(cls) -> "MinioObjectStore":
        return cls(
            bucket=require_env(BUCKET_ENV),
            client=build_client(
                require_env(ENDPOINT_ENV), require_env(ACCESS_KEY_ENV), require_env(SECRET_KEY_ENV)
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    def put(self, key: str, body: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=body, ContentType=content_type
        )
        logger.debug("put %s (%d bytes)", key, len(body))

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status in (403, 404):  # 없는 객체는 권한에 따라 403 으로도 온다
                return False
            raise
        return True
