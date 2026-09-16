"""pytest 공통 설정. Airflow 를 import 하기 전에 홈 디렉터리와 설정을 격리한다."""

import os
import tempfile

_AIRFLOW_HOME = tempfile.mkdtemp(prefix="airflow-test-")
os.environ.setdefault("AIRFLOW_HOME", _AIRFLOW_HOME)
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__DEFAULT_TIMEZONE", "Asia/Seoul")


# --- 수집 테스트 공용 도구 -------------------------------------------------
# 실제로 자지 않고 간격을 검증하려고 시계와 sleep 을 주입한다.

import pathlib  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


class FakeClock:
    """잔 만큼 시간이 흐른다. 몇 초 잤는지 기록한다."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture(autouse=True)
def _no_real_http(monkeypatch, request):
    """테스트가 실제 사이트를 치지 못하게 httpx 의 실제 전송을 막는다.

    수집 코드가 밖으로 나가는 길은 `CollectSession` 의 httpx 하나다. 테스트는 `MockTransport`
    를 끼우므로 이 막음에 닿지 않는다. 2026-09-14 에 인자 검사가 없던 백필 테스트가 진짜 세션을
    열어 Algolia 를 2분간 쳤다 — 그런 테스트가 네트워크 대신 여기서 즉시 실패한다.
    """

    if request.node.get_closest_marker("allow_network"):
        return

    def refuse(self, request):
        raise AssertionError(f"테스트가 실제 네트워크를 쳤다: {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def feed_bytes():
    def read(name: str) -> bytes:
        return (FIXTURES / "rss" / name).read_bytes()

    return read


@pytest.fixture
def listing_bytes():
    def read(name: str) -> bytes:
        return (FIXTURES / "listing" / name).read_bytes()

    return read


@pytest.fixture
def api_bytes():
    def read(name: str) -> bytes:
        return (FIXTURES / "api" / name).read_bytes()

    return read


@pytest.fixture
def mock_transport():
    """`handler(request) -> httpx.Response` 를 httpx 에 끼우는 공장."""

    def make(handler) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    return make


@pytest.fixture
def robots_allow_all():
    """robots.txt 요청이면 전부 허용하는 응답, 아니면 None 을 주는 도우미."""

    def maybe(request: httpx.Request) -> httpx.Response | None:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return None

    return maybe
