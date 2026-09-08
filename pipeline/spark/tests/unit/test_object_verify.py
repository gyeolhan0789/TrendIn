"""객체 검증 ([02 §3]). MinIO 없이 검사한다 ([09 §4] 층 1).

**실제 fixture 바이트를 쓴다.** checksum 대조가 진짜로 맞는지는 손으로 만든 해시로는
확인할 수 없다 — 생산 측이 `events.py` 로 만든 메시지와 `article_bytes()` 로 만든 객체가
짝이 맞는지가 이 단계의 전부다.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from trendin.spark.ingest.objects import verify

CONTRACT = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "contract"
OBJECTS = CONTRACT / "objects"


@pytest.fixture(scope="module")
def event() -> dict:
    return json.loads((CONTRACT / "article-event.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def body(event) -> bytes:
    return (OBJECTS / event["object_key"]).read_bytes()


def fetcher(objects: dict[tuple[str, str], bytes]):
    """`(bucket, key) -> bytes` 표. 없는 키는 `None` — 저장소가 404 를 주는 것과 같다."""

    def _fetch(bucket: str, key: str) -> bytes | None:
        return objects.get((bucket, key))

    return _fetch


def store(event: dict, body: bytes) -> dict[tuple[str, str], bytes]:
    return {(event["bucket"], event["object_key"]): body}


def test_정상_기사는_통과한다(event, body):
    assert verify(fetcher(store(event, body)), event) == (None, "")


def test_객체가_없으면_OBJECT_NOT_FOUND(event, body):
    error_type, detail = verify(fetcher({}), event)

    assert error_type == "OBJECT_NOT_FOUND"
    assert event["object_key"] in detail  # 어느 키인지 안 적으면 사람이 못 찾는다


def test_바이트가_한_글자_달라지면_CHECKSUM_MISMATCH(event, body):
    tampered = body.replace(b'"title"', b'"titlE"', 1)
    assert tampered != body

    error_type, _ = verify(fetcher(store(event, tampered)), event)

    assert error_type == "CHECKSUM_MISMATCH"


def test_재직렬화한_바이트는_불일치한다(event, body):
    """파싱 후 다시 직렬화하면 키 순서·공백·이스케이프가 달라져 전량 불일치한다.

    받은 바이트를 그대로 해싱해야 한다는 것을 여기가 고정한다 ([02 §3]).
    """
    reserialized = json.dumps(json.loads(body), ensure_ascii=True).encode("utf-8")

    error_type, _ = verify(fetcher(store(event, reserialized)), event)

    assert error_type == "CHECKSUM_MISMATCH"


def test_checksum_은_맞는데_다른_기사면_ARTICLE_CONTRACT_VIOLATION(event, body):
    """checksum 은 "내용이 온전한가" 에만 답한다. 온전한 **엉뚱한** 객체를 가리키면
    체크섬은 통과하고 도메인·소스가 어긋난 문서가 들어온다."""
    other = dict(json.loads(body))
    other["source"] = "wkorea"
    other_bytes = json.dumps(other, ensure_ascii=False).encode("utf-8")
    # 메시지가 그 바이트를 정확히 가리키게 해서 checksum 단계를 통과시킨다.
    pointed = event | {"checksum": "sha256-" + hashlib.sha256(other_bytes).hexdigest()}

    error_type, detail = verify(fetcher(store(pointed, other_bytes)), pointed)

    assert error_type == "ARTICLE_CONTRACT_VIOLATION"
    assert "source" in detail


def test_필수_필드가_없으면_ARTICLE_CONTRACT_VIOLATION(event, body):
    broken = {k: v for k, v in json.loads(body).items() if k != "published_at"}
    broken_bytes = json.dumps(broken, ensure_ascii=False).encode("utf-8")
    pointed = event | {"checksum": "sha256-" + hashlib.sha256(broken_bytes).hexdigest()}

    error_type, detail = verify(fetcher(store(pointed, broken_bytes)), pointed)

    assert error_type == "ARTICLE_CONTRACT_VIOLATION"
    assert "published_at" in detail


def test_JSON_이_아니면_ARTICLE_CONTRACT_VIOLATION(event):
    """checksum 은 통과했는데 JSON 이 아니다 — 생산자가 그 바이트를 그대로 저장했다는 뜻."""
    junk = b"<html>not json</html>"
    pointed = event | {"checksum": "sha256-" + hashlib.sha256(junk).hexdigest()}

    error_type, _ = verify(fetcher(store(pointed, junk)), pointed)

    assert error_type == "ARTICLE_CONTRACT_VIOLATION"


def test_순서는_존재_체크섬_내용이다(event):
    """없는 객체를 "체크섬 불일치" 로 보고하면 생산자가 저장이 아니라 해시를 의심한다."""
    error_type, _ = verify(fetcher({}), event | {"checksum": "sha256-deadbeef"})

    assert error_type == "OBJECT_NOT_FOUND"
