"""피드 5곳의 article.json·raw 골든 (S15P21A102-284).

소스 정의를 코드 튜플에서 TOML 프로필로 옮겨도 같은 기사가 나와야 한다. 필드 몇 개를
골라 보는 시험은 옮기면서 생긴 차이를 놓치므로, 저장되는 바이트 전체를 고정해 둔다.

골든은 옮기기 전 코드로 떴다. 출력이 **의도대로** 바뀌는 작업(예: 285 의 HTML 조각
본문)은 `UPDATE_GOLDEN=1 pytest tests/fashion/test_rss_golden.py` 로 다시 뜨고, 그 diff 가
무엇이 바뀌었는지의 리뷰 근거가 된다.
"""

import hashlib
import json
import os
import pathlib
from datetime import datetime, timezone

import httpx
import pytest

from trendin.common.collect.flow import article_bytes
from trendin.common.collect.session import CollectSession
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import RssAdapter

GOLDEN = pathlib.Path(__file__).resolve().parent.parent / "fixtures" / "rss" / "golden"
MEASURED = ["vogue", "gqkorea", "wkorea", "allure", "marieclaire"]
COLLECTED_AT = datetime(2026, 9, 3, 5, 0, tzinfo=timezone.utc)


def snapshot(key: str, feed: bytes, clock) -> dict:
    source = sources.get(key)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=feed)

    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        transport=httpx.MockTransport(handler),
        clock=clock,
        sleep=clock.sleep,
    ) as session:
        adapter = RssAdapter(source, session, now=lambda: COLLECTED_AT)
        result = adapter.discover()
        articles = []
        for candidate in result.candidates:
            raw, article = adapter.materialize(candidate)
            articles.append(
                {
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "article": json.loads(article_bytes(article)),
                }
            )
    return {
        "page_2_url": adapter.page_url(2),
        "failures": len(result.failures),
        "articles": articles,
    }


@pytest.mark.parametrize("key", MEASURED)
def test_피드_소스의_저장_결과가_골든과_같다(key, clock, feed_bytes):
    actual = snapshot(key, feed_bytes(f"{key}.xml"), clock)
    path = GOLDEN / f"{key}.json"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert actual == json.loads(path.read_text(encoding="utf-8"))
