"""robots.txt 판정 (불변식 1).

상수로 박지 않고 실행 때 받는다. 박아 두면 사이트가 규칙을 강화해도 우리가 모른 채
계속 치게 되고, 그게 불변식 1 이 막으려는 상황이다. 소스당 한 번이라 요청 비용은 무시할
수준이다.
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser


class RobotsCache:
    """호스트별 robots.txt 를 한 번만 받아 기억한다.

    `fetch` 는 robots.txt 본문을 돌려주거나, 받을 수 없으면 None 을 돌려준다.
    None 이면 전부 허용으로 본다 — robots.txt 가 없는 호스트의 표준 처리다.
    """

    def __init__(self, fetch: Callable[[str], str | None]) -> None:
        self._fetch = fetch
        self._by_origin: dict[str, RobotFileParser | None] = {}

    def can_fetch(self, user_agent: str, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._by_origin:
            body = self._fetch(f"{origin}/robots.txt")
            if body is None:
                self._by_origin[origin] = None
            else:
                parser = RobotFileParser()
                parser.parse(body.splitlines())
                self._by_origin[origin] = parser
        parser = self._by_origin[origin]
        return True if parser is None else parser.can_fetch(user_agent, url)
