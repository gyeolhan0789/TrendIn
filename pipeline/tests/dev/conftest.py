"""dev 수집 테스트 공용 도구. Algolia 를 흉내 내는 가짜 서버."""

import urllib.parse

import httpx
import pytest


class FakeAlgolia:
    """`numericFilters` 구간에 드는 story 를 Algolia 처럼 돌려준다.

    한 질의에 최대 1000건만 주고 `nbHits` 에는 전체 수를, `nbPages` 에는 1 을 싣는다 —
    2026-09-14 7일 구간 실측이 그 모양이었다(nbHits 7018, nbPages 1, hit 1000).
    """

    CAP = 1000

    def __init__(self, created: list[int]) -> None:
        self.hits = [
            {
                "objectID": str(100000 + i),
                "created_at_i": t,
                "title": f"story {i}",
                "_tags": ["story"],
            }
            for i, t in enumerate(created)
        ]
        self.windows: list[tuple[int, int, int]] = []  # (since, until, 준 건수)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        bounds = urllib.parse.parse_qs(request.url.query.decode())["numericFilters"][0].split(",")
        since = int(bounds[0].removeprefix("created_at_i>="))
        until = int(bounds[1].removeprefix("created_at_i<"))
        matched = sorted(
            (h for h in self.hits if since <= h["created_at_i"] < until),
            key=lambda h: -h["created_at_i"],
        )
        page = matched[: self.CAP]
        self.windows.append((since, until, len(page)))
        body = {"hits": page, "nbHits": len(matched), "nbPages": 1, "hitsPerPage": 1000, "page": 0}
        return httpx.Response(200, json=body)


@pytest.fixture
def fake_algolia():
    return FakeAlgolia
