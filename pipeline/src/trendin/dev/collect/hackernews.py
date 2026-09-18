"""Hacker News 어댑터 (S15P21A102-165, 설계 문서 확정 1·3).

Algolia `search_by_date` 한 번이 발견과 취득을 같이 끝낸다 — hit 하나가 곧 raw 다.
피드 소스와 같은 모양이라 `discover` 는 id 만 뽑고 정규화는 `materialize` 로 미룬다.

**본문을 싣지 않는다.** Ask HN 류의 `story_text` 는 raw 에 그대로 남지만 `body_text` 로
옮기지 않는다. dev 문서에 본문을 쓸지는 Spark 의 추출 경로 결정(한계 19)이 정하고, 수집이
10% 에만 본문을 넣으면 그 결정을 앞질러 버린다. 필요해지면 raw 에서 다시 만든다.

**점수는 수집 시각의 스냅샷이다.** 막 올라온 글은 `score` 가 거의 1 이고 v1 은 받은 글을
갱신하지 않는다. 스팸 판정도 수집이 하지 않는다 — 품질 판정은 Spark 몫이다.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

from trendin.common.collect.article import Article
from trendin.common.collect.contracts import Candidate, DiscoverResult, Failure, SourceDef
from trendin.common.collect.keys import raw_key
from trendin.common.collect.session import CollectSession
from trendin.common.collect.urls import clean_url

logger = logging.getLogger("trendin.collect.hackernews")

# 주기 실행이 매번 되돌아보는 창. 30분 주기에서 11번 연속 빠져도 잃지 않고, 시간당 ~30건이면
# 한 번에 ~200건이라 아래 상한 안에 든다. 겹치는 글은 장부가 거른다.
WINDOW = timedelta(hours=6)
# Algolia 가 한 질의에 주는 최대치. 넘치면 `nbPages` 는 1 그대로이고 뒤 페이지는 거부된다.
HITS_PER_PAGE = 1000
ITEM_URL = "https://news.ycombinator.com/item?id={}"
# `_tags` 중 글의 모양을 말하는 것만 분류로 싣는다. `front_page` 는 시간에 따라 붙었다
# 떨어지는데 v1 은 글을 갱신하지 않아서, 받은 순간의 우연한 값으로 굳는다.
CATEGORY_TAGS = frozenset({"show_hn", "ask_hn"})


def _epoch(moment: datetime) -> int:
    return int(moment.timestamp())


class HackerNewsAdapter:
    """Algolia 로 story 를 찾는다. 저장·발급·중복 판정은 모른다."""

    def __init__(
        self,
        source: SourceDef,
        session: CollectSession,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.source = source
        self._session = session
        self._now = now or (lambda: datetime.now(timezone.utc))

    def discover(self, page: int | None = None) -> DiscoverResult:
        if page is not None:
            raise ValueError("hn 에는 페이지가 없다 — 과거분은 discover_range 로 구간을 준다")
        until = self._now()
        return self.discover_range(until - WINDOW, until)

    def discover_range(self, since: datetime, until: datetime) -> DiscoverResult:
        """`since <= created_at < until` 인 story 를 전부 찾는다."""
        collected_at = self._now()
        candidates: list[Candidate] = []
        failures: list[Failure] = []
        start, end = _epoch(since), _epoch(until)
        for hit in self._search(start, end):
            article_id = hit.get("objectID")
            created = hit.get("created_at_i")
            if not article_id or not isinstance(created, int):
                failures.append(
                    Failure(
                        self.source.key,
                        "discover",
                        str(article_id or "?"),
                        "objectID·created_at_i 가 없다",
                    )
                )
                continue
            if not start <= created < end:
                # 경계는 질의 문자열로 Algolia 에 맡기지만 받은 쪽에서도 지킨다. 조각끼리 겹치거나
                # 창 밖 글이 섞이면 "구간을 주면 그 안의 story" 라는 계약이 조용히 깨진다.
                failures.append(
                    Failure(
                        self.source.key,
                        "discover",
                        str(article_id),
                        f"요청 구간 밖이다: created_at_i={created} ∉ [{start}, {end})",
                    )
                )
                continue
            candidates.append(
                Candidate(
                    source=self.source.key,
                    article_id=str(article_id),
                    url=_article_url(hit),
                    raw=json.dumps(hit, ensure_ascii=False).encode("utf-8"),
                    raw_ext="json",
                    collected_at=collected_at,
                    published_at=datetime.fromtimestamp(created, timezone.utc),
                )
            )
        logger.info(
            "%s: 후보 %d건, 실패 %d건 (%s ~ %s)",
            self.source.key,
            len(candidates),
            len(failures),
            since.isoformat(),
            until.isoformat(),
        )
        return DiscoverResult(candidates, failures)

    def _search(self, since: int, until: int) -> list[dict[str, Any]]:
        """구간 하나를 묻는다. 상한만큼 찼으면 그 응답을 버리고 반씩 다시 묻는다.

        2026-09-14 7일 구간 실측에서 hit 1000 에 `nbPages` 는 1 이었고, 페이지를 넘기면
        "1000건까지만" 이라며 거부했다. 판정을 `nbHits` 에 기대지 않는다 — Algolia 는 그 값이
        추정일 수 있다고 `exhaustive.nbHits` 로 따로 알린다. 추정이 부풀면 1000건 안 되는
        구간도 1초까지 쪼개다 죽는다. 딱 1000건인 구간을 한 번 더 쪼개는 값은 요청 두 번이다.
        """
        query = urlencode(
            {
                "tags": "story",
                "numericFilters": f"created_at_i>={since},created_at_i<{until}",
                "hitsPerPage": HITS_PER_PAGE,
            }
        )
        # 질의 URL 이 매번 바뀌어 조건부 요청 기록이 실행마다 한 줄씩 쌓이기만 한다.
        response = self._session.get(f"{self.source.discover_url}?{query}", conditional=False)
        hits = json.loads(response.body)["hits"]
        if len(hits) < HITS_PER_PAGE:
            return hits
        if until - since <= 1:
            # 1초에 1000건 — 더 쪼갤 수 없다. 조용히 잘라 넘기지 않는다.
            raise ValueError(f"1초 구간이 상한을 넘었다: created_at_i={since}")
        middle = (since + until) // 2
        logger.info("%s: %d~%d 가 상한에 찼다 — 쪼갠다", self.source.key, since, until)
        return self._search(middle, until) + self._search(since, middle)

    def materialize(self, candidate: Candidate) -> tuple[bytes, Article]:
        if candidate.published_at is None or candidate.raw is None:
            raise ValueError(f"발견이 발행일·raw 를 안 실었다: {candidate.article_id}")
        hit = json.loads(candidate.raw)
        article = Article(
            domain=self.source.domain,
            source=self.source.key,
            route=self.source.route,
            article_id=candidate.article_id,
            url=candidate.url,
            title=hit.get("title") or "",
            published_at=candidate.published_at,
            collected_at=candidate.collected_at,
            raw_key=raw_key(
                self.source.domain,
                self.source.key,
                self.source.route,
                candidate.published_at,
                candidate.article_id,
                ext="json",
            ),
            content_sha256=hashlib.sha256(candidate.raw).hexdigest(),
            categories=[tag for tag in hit.get("_tags", []) if tag in CATEGORY_TAGS],
            author=hit.get("author"),
            extra={
                "score": hit.get("points"),
                "descendants": hit.get("num_comments"),
                "by": hit.get("author"),
                # `url` 이 대체값(HN 항목)인지 원문 링크인지를 소비자가 추측하지 않게 한다.
                "external_url": hit.get("url") or None,
            },
        )
        return candidate.raw, article


def _article_url(hit: dict[str, Any]) -> str:
    external = hit.get("url")
    return clean_url(external) if external else ITEM_URL.format(hit.get("objectID"))
