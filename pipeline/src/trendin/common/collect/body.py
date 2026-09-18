"""기사 페이지에서 본문을 얻는다 (설계 문서 확정 2, S15P21A102-285).

순서는 **ld+json `articleBody` → trafilatura → 피드 본문**이다. 프로필에 본문 위치를 적지
않는다 — 사이트가 늘수록 리뷰할 규칙이 는다(`source-discovery.md` #3.3 철회).

**ld+json 을 먼저 보지만, 티저면 trafilatura 로 넘어간다.** 2026-09-16 실측에서 WWD·BoF 의
`articleBody` 는 63~209자짜리 앞부분이었고 trafilatura 는 같은 페이지에서 1,600~3,100자를
뽑았다. 그래서 둘을 다 만들고, ld+json 글자 수가 trafilatura 의 `LD_MIN_RATIO` 이상일
때만 ld+json 을 쓴다. 발행처가 정리한 텍스트라 잡음이 없어서 먼저 본다. 실측 비율 판정(전문
피드 = 0.7)과 같은 값이다.

**유료 표시는 기사 노드 최상위 `isAccessibleForFree` 만 본다.** 페이지 어딘가에 문자열이
있다고 치면 추천 위젯 같은 다른 노드의 값에 기사가 끌려간다. 기사 노드가 여럿이면 하나라도
거짓이면 유료다 — 2026-09-17 WWD 페이지는 `NewsArticle` 을 두 블록에 싣고 두 번째에만
`"false"` 를 적었다. 유료 표시 기사는 본문을 만들지
않는다(불변식 2) — HTML 에 본문이 실려 와도 같다.

**피드 본문이 페이지에서 뽑은 것보다 길면 피드 본문을 쓴다.** 전문 피드에서 페이지 추출이
짧아지는 일이 있어서다(2026-09-17 실측, `extract_body` 주석). 요약 피드는 피드 쪽이 짧아
페이지 추출이 이긴다.

세 경로 모두 HTML 조각을 낸다(#5.3). 공통 잡음 제거는 `html_fragment` 가 한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from typing import Any, Literal

import trafilatura
from trafilatura.utils import decode_file

from trendin.common.collect.html_text import html_fragment, text_length

LD_JSON_TYPES = frozenset({"NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting"})
LD_MIN_RATIO = 0.7

_LD_BLOCK = re.compile(r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>')
_BODY = re.compile(r"(?is)<body[^>]*>(.*)</body>")

Via = Literal["ld_json", "trafilatura", "feed"]


def decode_page(raw: bytes) -> str:
    """받은 바이트를 문자열로. 인코딩은 trafilatura 가 헤더 없이 추정한다(EUC-KR 소스 대비)."""
    return decode_file(raw)


def _types(value: Any) -> set[str]:
    """`@type` 은 문자열일 수도 배열일 수도 있다."""
    if isinstance(value, str):
        return {value}
    return {v for v in (value or []) if isinstance(v, str)}


def _nodes(data: Any):
    """최상위 배열과 `@graph` 안까지. 그보다 깊이는 기사 노드가 아니다."""
    for node in data if isinstance(data, list) else [data]:
        if not isinstance(node, dict):
            continue
        yield node
        graph = node.get("@graph")
        if isinstance(graph, list):
            yield from (n for n in graph if isinstance(n, dict))


def find_ld_articles(html: str) -> list[dict[str, Any]]:
    """기사 페이지의 ld+json 기사 노드 전부. 페이지에 나온 순서다."""
    found = []
    for block in _LD_BLOCK.findall(html):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        found.extend(n for n in _nodes(data) if LD_JSON_TYPES.intersection(_types(n.get("@type"))))
    return found


def is_paywalled(nodes: list[dict[str, Any]]) -> bool:
    """기사 노드 최상위 `isAccessibleForFree` 가 하나라도 거짓인가. 문자열 `"False"` 도 거짓이다."""
    for node in nodes:
        value = node.get("isAccessibleForFree")
        if value is False or (isinstance(value, str) and value.strip().lower() == "false"):
            return True
    return False


def ld_body_fragment(nodes: list[dict[str, Any]]) -> str:
    """`articleBody` 가 있는 첫 노드. 평문이라 줄마다 이스케이프해 `<p>` 로 감싼다."""
    body = next((n["articleBody"] for n in nodes if isinstance(n.get("articleBody"), str)), None)
    if body is None:
        return ""
    paragraphs = [line.strip() for line in body.splitlines() if line.strip()]
    return html_fragment("".join(f"<p>{escape(p, quote=False)}</p>" for p in paragraphs))


def trafilatura_fragment(html: str, url: str | None = None) -> str:
    extracted = trafilatura.extract(html, url=url, output_format="html", include_comments=False)
    if not extracted:
        return ""
    match = _BODY.search(extracted)
    return html_fragment(match.group(1) if match else extracted)


@dataclass(frozen=True, slots=True)
class PageBody:
    nodes: list[dict[str, Any]]  # ld+json 기사 노드. 없으면 빈 목록
    paywalled: bool
    body_text: str | None  # HTML 조각. 유료 표시면 늘 None
    via: Via | None


def extract_body(html: str, *, url: str | None = None, feed_body: str = "") -> PageBody:
    """기사 페이지 HTML 에서 본문 조각을 고른다. `feed_body` 는 피드가 준 본문 HTML 이다.

    **피드 본문이 페이지에서 뽑은 것보다 길면 피드 본문을 쓴다** (2026-09-17 실측으로 정함).
    전문 피드에서 페이지 추출이 짧아지는 일이 있었다 — L'Officiel 2,902자 → 368자, vogue
    715자 → 508자. 반대로 요약 피드는 피드 쪽이 짧아 페이지 추출이 이긴다. 그래서 "피드가
    전문인지"를 미리 판정하지 않고도 두 실패를 다 피한다.
    """
    nodes = find_ld_articles(html)
    if is_paywalled(nodes):
        return PageBody(nodes, True, None, None)

    ld = ld_body_fragment(nodes)
    extracted = trafilatura_fragment(html, url)
    if ld and text_length(ld) >= LD_MIN_RATIO * text_length(extracted):
        page, via = ld, "ld_json"
    else:
        page, via = extracted, "trafilatura"

    feed = html_fragment(feed_body)
    if text_length(feed) > text_length(page):
        return PageBody(nodes, False, feed, "feed")
    return PageBody(nodes, False, page or None, via if page else None)
