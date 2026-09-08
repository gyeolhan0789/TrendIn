"""`io/objects.fetch` 의 오류 분기 ([02 §3]). MinIO 없이 검사한다 ([09 §4] 층 1).

`get_object` 를 가짜로 바꿔 `ClientError` 를 그대로 던진다 — 여기서 볼 것은 바이트가 아니라
**어떤 오류를 `None` 으로 삼키고 어떤 것을 올리는가** 뿐이다.

이 파일이 있는 이유는 세 분기의 결과가 되돌릴 수 있는지가 서로 다르기 때문이다. 없는 키는
정상 경로(DLQ)이고, 버킷 부재와 403 은 우리가 저장소를 잘못 보고 있다는 뜻이라 배치를
멈춰야 한다. 삼키면 처리 이력에 `stage=object` 로 적히고 오프셋도 전진해서 설정을 고쳐
재실행해도 복구되지 않는다.
"""

from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from trendin.spark.io.objects import BucketNotFound, StoreConfig, fetch

STORE = StoreConfig(
    endpoint="http://localhost:9000",
    access_key="key",
    secret_key="secret",
)


def client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        "GetObject",
    )


@pytest.fixture
def raising(monkeypatch):
    """`fetch` 가 부르는 클라이언트를 주어진 오류만 던지는 가짜로 바꾼다."""

    def _install(exc: Exception):
        class _Client:
            def get_object(self, **_kwargs):
                raise exc

        monkeypatch.setattr("trendin.spark.io.objects.client", lambda _store: _Client())

    return _install


def test_없는_키는_None(raising):
    raising(client_error("NoSuchKey", 404))

    assert fetch(STORE, "raw", "missing.json") is None


def test_없는_버킷은_BucketNotFound(raising):
    """**404 라고 다 `None` 이 아니다.** 버킷이 없으면 그 배치의 기사 이벤트가 전부 걸리므로
    이벤트 하나의 DLQ 사유로 옮길 수 없다."""
    raising(client_error("NoSuchBucket", 404))

    with pytest.raises(BucketNotFound):
        fetch(STORE, "typo-raw", "a.json")


def test_BucketNotFound_는_버킷과_endpoint_를_적는다(raising):
    """버킷 이름은 이벤트에서, endpoint 는 설정에서 온다. 둘 중 어느 쪽이 틀렸는지는
    사람이 갈라야 하므로 메시지에 둘 다 있어야 한다."""
    raising(client_error("NoSuchBucket", 404))

    with pytest.raises(BucketNotFound) as caught:
        fetch(STORE, "typo-raw", "a.json")

    assert "typo-raw" in str(caught.value)
    assert STORE.endpoint in str(caught.value)


def test_코드가_없는_404_는_None(raising):
    """MinIO 가 코드를 안 주는 경우도 있어 상태 코드만으로도 판단한다. 이 분기가 살아 있는
    한 `NoSuchBucket` 검사는 그보다 **먼저** 와야 한다."""
    raising(client_error("", 404))

    assert fetch(STORE, "raw", "missing.json") is None


def test_403_은_그대로_올린다(raising):
    """정책이 잘못 붙은 날 배치가 통째로 `OBJECT_NOT_FOUND` DLQ 가 되면 생산자 잘못으로
    보인다 — 우리 키 설정이 틀린 것인데."""
    raising(client_error("AccessDenied", 403))

    with pytest.raises(ClientError):
        fetch(STORE, "raw", "a.json")
