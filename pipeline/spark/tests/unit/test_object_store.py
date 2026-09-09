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

from trendin.spark.io.objects import (
    BucketNotFound,
    StoreConfig,
    fetch,
    head_metadata,
    list_keys,
    list_prefixes,
)

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


@pytest.fixture
def listing_raising(monkeypatch):
    """목록 조회가 부르는 페이지네이터를 주어진 오류만 던지는 가짜로 바꾼다.

    **페이지네이터가 지연 평가라는 점이 중요하다.** `paginate()` 자체는 오류를 내지 않고
    순회할 때 낸다 — 그래서 `_listing` 이 `list()` 로 감싸 예외를 그 함수의 규약 안으로
    끌어온다. 이 가짜도 같은 형태로 던져 그 배선을 검사한다.
    """

    def _install(exc: Exception):
        class _Paginator:
            def paginate(self, **_kwargs):
                def _pages():
                    raise exc
                    yield  # pragma: no cover — 제너레이터로 만들기 위한 줄

                return _pages()

        class _Client:
            def get_paginator(self, _name):
                return _Paginator()

        monkeypatch.setattr("trendin.spark.io.objects.client", lambda _store: _Client())

    return _install


@pytest.fixture
def head_raising(monkeypatch):
    def _install(exc: Exception):
        class _Client:
            def head_object(self, **_kwargs):
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


# --- 목록 조회 ([02 §6] 모드 B) -------------------------------------------


@pytest.mark.parametrize("listing", [list_prefixes, list_keys])
def test_목록_조회도_없는_버킷을_올린다(listing_raising, listing):
    """**삼키면 백필이 조용히 빈손으로 끝난다.** 목록이 비면 "그 범위에 기사가 없다" 와
    구분되지 않아서, `--source objects` 가 아무것도 하지 않고 정상 종료한다.

    사람이 범위를 정해 부른 복구 작업이라, 그 침묵은 "복구했다" 로 읽힌다.
    """
    listing_raising(client_error("NoSuchBucket", 404))

    with pytest.raises(BucketNotFound):
        listing(STORE, "typo-raw", "fashion/")


@pytest.mark.parametrize("listing", [list_prefixes, list_keys])
def test_목록_조회의_403_은_그대로_올린다(listing_raising, listing):
    """정책이 잘못 붙은 것을 "객체가 없다" 로 보고하면 엉뚱한 곳을 보게 된다."""
    listing_raising(client_error("AccessDenied", 403))

    with pytest.raises(ClientError):
        listing(STORE, "raw", "fashion/")


# --- 메타데이터 조회 -------------------------------------------------------


def test_HEAD_의_코드_없는_404_는_None(head_raising):
    """목록을 만든 뒤 보관 기간이 지나 사라진 객체다 ([02 §6]).

    `HEAD` 응답에는 본문이 없어 XML 에러 코드가 오지 않고, botocore 가 `Error.Code` 를
    상태 코드 문자열로 채운다. 그래서 이 경로가 실제로 자주 온다.
    """
    head_raising(client_error("404", 404))

    assert head_metadata(STORE, "raw", "gone/article.json") is None


def test_HEAD_도_코드가_오면_버킷_부재를_올린다(head_raising):
    """`HEAD` 는 대개 코드를 주지 않지만, **주는 경우에 삼키면** b277af9 가 없앤 경로가
    되살아난다 — 버킷 부재가 키 부재로 도착한다.

    그래서 코드를 상태보다 먼저 본다. 순서가 뒤집히면 `_NOT_FOUND` 의 `"404"` 가 다시 삼킨다.
    """
    head_raising(client_error("NoSuchBucket", 404))

    with pytest.raises(BucketNotFound):
        head_metadata(STORE, "typo-raw", "a/article.json")


def test_메타데이터가_없으면_빈_사전이다(monkeypatch):
    """**`None` 과 빈 사전을 가른다.** 없는 객체와 "메타데이터 규약 전에 올라간 객체" 는
    다르게 처리한다 ([02 §6]) — 후자는 checksum 검증을 건너뛰고 재처리한다.

    합치면 옛 객체를 재처리에서 통째로 버린다.
    """

    class _Client:
        def head_object(self, **_kwargs):
            return {}

    monkeypatch.setattr("trendin.spark.io.objects.client", lambda _store: _Client())

    assert head_metadata(STORE, "raw", "old/article.json") == {}


def test_메타데이터_이름을_소문자로_접는다(monkeypatch):
    """S3 가 헤더 이름의 대소문자를 보장하지 않는다. 접지 않으면 `content-sha256` 을
    못 찾아 백필이 전량 "checksum 없음" 으로 센다."""

    class _Client:
        def head_object(self, **_kwargs):
            return {"Metadata": {"Content-SHA256": "abc", "Collected-At": "2026-09-03"}}

    monkeypatch.setattr("trendin.spark.io.objects.client", lambda _store: _Client())

    assert head_metadata(STORE, "raw", "a/article.json") == {
        "content-sha256": "abc",
        "collected-at": "2026-09-03",
    }
