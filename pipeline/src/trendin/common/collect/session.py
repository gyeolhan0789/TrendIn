"""수집 요청의 유일한 통로 (설계 문서 불변식 2·4, #9, `source-discovery.md` 불변식 18).

정책 검사를 함수로 흩어 두면 어댑터가 "부르기로 마음먹어야만" 지켜진다. 게이트를 지나야
요청이 나가게 만들면 금지된 요청은 애초에 불가능해지고, 테스트는 여기 하나만 겨누면 된다.

이 모듈은 airflow 를 import 하지 않는다 — 태스크 함수는 Airflow 없이 테스트한다는
pipeline/README.md 규약 12 때문이다. 예외를 Airflow 개념으로 옮기는 건 실행 흐름(167) 몫.

**로그인·인증 경로가 없다.** 헤더·쿠키·자격 증명을 받는 인자가 없고, 응답이 준 쿠키는
매 요청 뒤 버린다. 로그인 수집을 하려면 이 파일을 고쳐야 하고, 그 커밋이 리뷰에 올라온다
(불변식 2).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urlsplit

import httpx

from trendin.common.collect.contracts import ValidatorStore

logger = logging.getLogger("trendin.collect.session")

USER_AGENT = "TrendInBot/0.1 (non-profit student project; trend analysis)"

# 두산매거진 4곳이 이름으로 차단하는 봇들. 이 토큰이 든 UA 로는 세션을 만들 수 없다.
BLOCKED_UA_TOKENS = (
    "scrapy",
    "gptbot",
    "ccbot",
    "claudebot",
    "anthropic-ai",
    "google-extended",
    "bytespider",
    "perplexitybot",
)

HOST_INTERVAL_SECONDS = 3.0
TIMEOUT_SECONDS = 20.0
RETRIES = 2
RETRY_WAIT_SECONDS = 60.0
# 재시도하지 않는 상태코드. 그 실행에서 그 호스트를 멈춘다 (불변식 2).
BLOCKING_STATUSES = frozenset({403, 429})


class CollectError(Exception):
    """수집 요청이 정책이나 네트워크 때문에 실패했다."""


class BlockedUserAgent(CollectError):
    """이름으로 차단당하는 UA 다. 세션 생성 시점에 막는다."""


class UrlNotAllowed(CollectError):
    """소스 정의가 허용한 URL 범위 밖이다."""


class HostBlocked(CollectError):
    """403·429 를 받았다. 이 실행에서 이 호스트는 끝이다. 재시도하지 않는다."""


class FetchFailed(CollectError):
    """재시도를 다 쓰고도 못 받았다.

    `status` 는 마지막 응답의 상태코드다. 네트워크 오류로 끝났으면 None 이다. 부르는 쪽이
    404·410 처럼 "다시 쳐도 같은" 실패를 가르는 데 쓴다 (S15P21A102-312).
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: bytes
    headers: Mapping[str, str]
    not_modified: bool = False


def _is_blocked_ua(user_agent: str) -> bool:
    lowered = user_agent.lower()
    return any(token in lowered for token in BLOCKED_UA_TOKENS)


class CollectSession:
    """호스트 간격·허용 URL·조건부 요청·재시도를 한자리에서 강제한다.

    robots.txt 는 받지도 판정하지도 않는다. 2026-09-17 약관과 robots 를 판정 기준에서 뺐다
    (`web-collect.md` 기준 전환). 차단 우회 금지(불변식 2)는 위 강제들이 그대로 진다.

    같은 호스트 간격은 **이 프로세스 안에서만** 성립한다. 두 태스크가 같은 호스트를
    동시에 치지 않게 하는 건 실행 흐름(167)이 소스당 태스크 하나로 매핑해서 한다.
    """

    def __init__(
        self,
        *,
        user_agent: str = USER_AGENT,
        allowed_url_prefixes: tuple[str, ...] = (),
        validators: ValidatorStore | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        interval: float = HOST_INTERVAL_SECONDS,
        timeout: float = TIMEOUT_SECONDS,
        retries: int = RETRIES,
        retry_wait: float = RETRY_WAIT_SECONDS,
    ) -> None:
        if _is_blocked_ua(user_agent):
            raise BlockedUserAgent(f"이름으로 차단당하는 UA 다: {user_agent!r}")
        self.user_agent = user_agent
        self._allowed = tuple(allowed_url_prefixes)
        self._validators = validators
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._retries = retries
        self._retry_wait = retry_wait
        self._last_request: dict[str, float] = {}
        self._blocked_hosts: set[str] = set()
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=False,  # 따라가면 허용 URL 검사를 안 거친 곳을 친다 (불변식 18)
            transport=transport,
        )

    # --- 공개 ---------------------------------------------------------------

    def get(self, url: str, *, conditional: bool = True) -> Response:
        """정책을 전부 통과한 GET. 304 면 `not_modified` 가 선 응답을 돌려준다."""
        self._check_allowed(url)
        return self._request(url, conditional=conditional)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CollectSession":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- 내부 ---------------------------------------------------------------

    def _check_allowed(self, url: str) -> None:
        if not self._allowed:
            return
        if not url.startswith(self._allowed):
            raise UrlNotAllowed(f"허용 범위 밖이다: {url}")

    def _throttle(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is None:
            return
        waited = self._clock() - last
        if waited < self._interval:
            self._sleep(self._interval - waited)

    def _conditional_headers(self, url: str) -> dict[str, str]:
        if self._validators is None:
            return {}
        stored = self._validators.get(url)
        if not stored:
            return {}
        etag, last_modified = stored
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def _remember_validators(self, url: str, headers: Mapping[str, str]) -> None:
        if self._validators is None:
            return
        # 304 가 새 validator 를 실어 주면 그게 최신이다. 안 실어 주면 갱신할 게 없다.
        self._validators.put(url, headers.get("ETag"), headers.get("Last-Modified"))

    def _request(self, url: str, *, conditional: bool) -> Response:
        host = urlsplit(url).netloc
        if host in self._blocked_hosts:
            raise HostBlocked(f"이 실행에서 이미 멈춘 호스트다: {host}")

        headers = self._conditional_headers(url) if conditional else {}
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                self._sleep(self._retry_wait)
            self._throttle(host)
            try:
                response = self._client.get(url, headers=headers)
            except httpx.HTTPError as exc:  # 네트워크·타임아웃
                logger.warning(
                    "%s %s — 재시도 %d/%d",
                    type(exc).__name__,
                    url,
                    attempt + 1,
                    self._retries,
                )
                last_error = exc
                self._last_request[host] = self._clock()
                continue
            finally:
                # 받은 쿠키는 버린다. 다음 요청에 실리지 않는다.
                self._client.cookies.clear()
            self._last_request[host] = self._clock()

            if response.status_code in BLOCKING_STATUSES:
                self._blocked_hosts.add(host)
                logger.error("%s 를 받았다. %s 를 멈춘다: %s", response.status_code, host, url)
                raise HostBlocked(f"{response.status_code} 를 받았다. {host} 를 멈춘다: {url}")
            if response.status_code == 304:
                self._remember_validators(url, response.headers)
                logger.info("304 %s", url)
                return Response(304, b"", dict(response.headers), not_modified=True)
            if response.status_code >= 500:
                logger.warning(
                    "%s %s — 재시도 %d/%d",
                    response.status_code,
                    url,
                    attempt + 1,
                    self._retries,
                )
                last_error = FetchFailed(
                    f"{response.status_code}: {url}", status=response.status_code
                )
                continue
            if response.status_code >= 400:
                raise FetchFailed(f"{response.status_code}: {url}", status=response.status_code)

            self._remember_validators(url, response.headers)
            logger.info("%s %s (%dB)", response.status_code, url, len(response.content))
            return Response(response.status_code, response.content, dict(response.headers))

        raise FetchFailed(f"{self._retries + 1}회 시도했지만 못 받았다: {url}") from last_error
