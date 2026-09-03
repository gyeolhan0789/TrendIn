"""조건부 요청(304)용 validator 보관소.

163 은 계약만 정하고 실제 보관은 주입받는다. 여기 있는 구현은 probe·백필·테스트가 쓰는
한 프로세스짜리다. 실행 사이에 남기는 구현은 S15P21A102-167 이 끼운다.
"""

from __future__ import annotations


class InMemoryValidatorStore:
    """프로세스가 사는 동안만 기억한다."""

    def __init__(self) -> None:
        self._by_url: dict[str, tuple[str | None, str | None]] = {}

    def get(self, url: str) -> tuple[str | None, str | None] | None:
        return self._by_url.get(url)

    def put(self, url: str, etag: str | None, last_modified: str | None) -> None:
        if etag or last_modified:
            self._by_url[url] = (etag, last_modified)
