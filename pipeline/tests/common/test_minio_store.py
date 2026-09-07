"""MinIO 저장 (S15P21A102-158). `Stubber` 로 돌아 실제 저장소가 필요 없다."""

import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber

from trendin.common.collect.minio_store import MinioObjectStore, build_client

KEY = "fashion/vogue/rss/2026/09/03/857991/raw.xml"


@pytest.fixture
def store():
    client = build_client("http://minio:9000", "crawler", "secret")
    yield MinioObjectStore(bucket="raw-data", client=client)
    client.close()


def test_MinIO_는_path_방식_주소를_쓴다(store):
    """버킷을 호스트 이름에 붙이는 virtual-host 방식은 MinIO 에서 못 쓴다."""
    config = store._client.meta.config
    assert config.s3["addressing_style"] == "path"
    assert config.signature_version == "s3v4"


def test_put_이_content_type_과_메타데이터를_같이_보낸다(store):
    with Stubber(store._client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "raw-data",
                "Key": KEY,
                "Body": b"<item/>",
                "ContentType": "application/xml",
                "Metadata": {"collected-at": "2026-09-03T14:00:00+09:00"},
            },
        )
        store.put(KEY, b"<item/>", "application/xml", {"collected-at": "2026-09-03T14:00:00+09:00"})
        stub.assert_no_pending_responses()


def test_메타데이터가_없어도_요청이_나간다(store):
    with Stubber(store._client) as stub:
        stub.add_response(
            "put_object",
            {},
            {"Bucket": ANY, "Key": ANY, "Body": ANY, "ContentType": ANY, "Metadata": {}},
        )
        store.put(KEY, b"x", "application/xml")
        stub.assert_no_pending_responses()


def test_ASCII_아닌_메타데이터는_요청_전에_막는다(store):
    """객체 메타데이터는 latin-1 헤더로 실려 한글이 섞이면 요청이 깨진다."""
    with Stubber(store._client) as stub:
        with pytest.raises(ValueError, match="ASCII"):
            store.put(KEY, b"x", "application/xml", {"title": "제목"})
        stub.assert_no_pending_responses()  # 요청이 아예 안 나갔다


def test_있는_객체는_참이다(store):
    with Stubber(store._client) as stub:
        stub.add_response("head_object", {"ContentLength": 12}, {"Bucket": "raw-data", "Key": KEY})
        assert store.exists(KEY) is True


def test_빈_객체도_있는_것이다(store):
    """0 바이트도 정상 저장이다. 존재 판정을 크기로 하지 않는다."""
    with Stubber(store._client) as stub:
        stub.add_response("head_object", {"ContentLength": 0}, {"Bucket": ANY, "Key": ANY})
        assert store.exists(KEY) is True


def test_없는_객체는_거짓이다(store):
    with Stubber(store._client) as stub:
        stub.add_client_error("head_object", http_status_code=404, service_error_code="404")
        assert store.exists(KEY) is False


def test_403_은_없음이_아니다(store):
    """False 로 뭉개면 저장은 됐는데 장부에 안 적혀 다음 실행이 같은 기사를 또 받는다."""
    with Stubber(store._client) as stub:
        stub.add_client_error(
            "head_object", http_status_code=403, service_error_code="AccessDenied"
        )
        with pytest.raises(ClientError):
            store.exists(KEY)


def test_5xx_도_없음이_아니다(store):
    with Stubber(store._client) as stub:
        stub.add_client_error(
            "head_object", http_status_code=500, service_error_code="InternalError"
        )
        with pytest.raises(ClientError):
            store.exists(KEY)
