"""등록 프로브 — 새 피드 소스를 등록하기 전에 잰다 (S15P21A102-291).

    python -m trendin.fashion.collect.probe vogue_uk --check --header
    python -m trendin.fashion.collect.probe vogue_uk --check --page-param page

진짜 어댑터·세션으로 1페이지를 발견하고 표본 기사를 받는다. 페이지 넘김 파라미터가 있으면
2페이지와 피드 끝(999페이지)도 본다. 저장·발급은 하지 않는다. 출력은 표본별 줄과, 측정
표(`source-discovery.md` #4)에 붙일 마크다운 한 줄이다.

403·429 를 받으면 그 뒤로 아무것도 치지 않는다(불변식 2). 세션은 멈춘 호스트를 요청 없이
거절한다. 그 거절이 2페이지·피드 끝의 측정값으로 찍히지 않게 여기서도 멈춘다.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from trendin.common.collect.body import Via, decode_page, extract_body
from trendin.common.collect.contracts import ArticleFetchError, Candidate, DiscoverResult
from trendin.common.collect.html_text import text_length
from trendin.common.collect.session import FetchFailed, HostBlocked
from trendin.fashion.collect.rss import (
    _FORMATS,
    FeedParseError,
    RssAdapter,
    feed_format,
    parse_item,
)

END_PAGE = 999
BLOCKED = "차단"
UNPARSED = "파싱 실패"

HEADER = (
    "| key | country | 형식 | 1p 건수 | 1p 발행일 폭(일) | 본문 경로(표본별) | 본문 길이 중앙값 "
    "| 유료 n/N | 403 n/N | 저자 n/N | 2p | 끝 페이지 |\n"
    "|---|---|---|---:|---:|---|---:|---|---|---|---|---|"
)

Page2 = Literal["ok", "same_page", "not_older", "empty_or_404", "discover_failed"]


@dataclass(frozen=True, slots=True)
class Sample:
    article_id: str
    url: str
    published_at: datetime | None
    # 아래는 받았을 때만 뜻이 있다. 못 받았으면 `failure` 에 이유가 있다.
    via: Via | None = None
    body_length: int = 0
    author: bool = False
    paywalled: bool = False
    failure: str | None = None
    blocked: bool = False  # 403·429


@dataclass(frozen=True, slots=True)
class Report:
    key: str
    country: str
    format: str
    page1: list[Candidate]
    samples: list[Sample]
    # 페이지 넘김 파라미터가 없거나 차단으로 멈췄으면 None 이다.
    page2: Page2 | str | None = None
    page2_line: str = ""
    end: str | None = None


def check(adapter: RssAdapter, *, samples: int = 3) -> Report:
    source = adapter.source
    first = adapter.discover()
    page1 = first.candidates
    fmt = feed_format(parse_item(page1[0].raw)) if page1 else "-"

    taken: list[Sample] = []
    for candidate in page1[:samples]:
        sample = _sample(adapter, candidate)
        taken.append(sample)
        if sample.blocked:
            return Report(source.key, source.country, fmt, page1, taken)

    report = Report(source.key, source.country, fmt, page1, taken)
    if source.page_param is None:
        return report

    second = _discover(adapter, 2)
    verdict, line = _page2(page1, second)
    if second == BLOCKED:
        return Report(source.key, source.country, fmt, page1, taken, verdict, line)
    end = _discover(adapter, END_PAGE)
    if isinstance(end, DiscoverResult):
        end = "items" if end.candidates or end.failures else "empty"
    return Report(source.key, source.country, fmt, page1, taken, verdict, line, end)


def _sample(adapter: RssAdapter, candidate: Candidate) -> Sample:
    base = dict(
        article_id=candidate.article_id, url=candidate.url, published_at=candidate.published_at
    )
    try:
        raw, article = adapter.materialize(candidate)
    except ArticleFetchError as exc:
        return Sample(**base, failure=exc.reason, blocked=exc.blocking)
    except ValueError as exc:  # 발행일 없음, 허용 범위 밖 링크
        return Sample(**base, failure=str(exc))
    return Sample(
        **base,
        via=_via(raw, candidate),
        body_length=text_length(article.body_text or ""),
        author=article.author is not None,
        paywalled=bool(article.paywalled),
    )


def _via(raw: bytes, candidate: Candidate) -> Via | None:
    """`Article` 은 본문 경로를 싣지 않는다. 어댑터와 같은 입력으로 한 번 더 뽑는다."""
    entry = parse_item(candidate.raw)
    feed_body = entry.first(_FORMATS[feed_format(entry)].body)
    return extract_body(decode_page(raw), url=candidate.url, feed_body=feed_body).via


def _discover(adapter: RssAdapter, page: int) -> DiscoverResult | str:
    """페이지를 못 받았거나 피드로 못 읽었으면 그 사정을 문자열로 돌려준다."""
    try:
        return adapter.discover(page=page)
    except HostBlocked:
        return BLOCKED
    except FeedParseError:
        # 없는 페이지에 200 과 HTML 을 주는 사이트가 있다(houyhnhnm ?paged=999, 2026-09-18).
        return UNPARSED
    except FetchFailed as exc:
        return str(exc.status) if exc.status is not None else "오류"


def _page2(page1: list[Candidate], second: DiscoverResult | str) -> tuple[Page2 | str, str]:
    if isinstance(second, str):
        verdict = "empty_or_404" if second in ("404", "410") else second
        return verdict, f"2p: {second}"
    if not second.candidates:
        # 기사가 있는데 규칙이 id 를 못 뽑았으면 빈 페이지가 아니다.
        # 옛 글의 guid 모양이 다른 피드다(theindustry 2026-09-18).
        if second.failures:
            return "discover_failed", f"2p: 후보 0건, 발견 실패 {len(second.failures)}건"
        return "empty_or_404", "2p: 0건"
    ids1 = {c.article_id for c in page1}
    ids2 = {c.article_id for c in second.candidates}
    oldest1 = min((c.published_at for c in page1 if c.published_at), default=None)
    newest2 = max((c.published_at for c in second.candidates if c.published_at), default=None)
    older = oldest1 is not None and newest2 is not None and newest2 < oldest1
    if ids2 == ids1:
        verdict = "same_page"
    elif not older:
        verdict = "not_older"
    else:
        verdict = "ok"
    line = (
        f"2p: {len(second.candidates)}건, 1p 와 겹침 {len(ids1 & ids2)}, "
        f"1p 보다 오래됨 {'예' if older else '아니오'}"
    )
    return verdict, line


def sample_lines(report: Report) -> list[str]:
    lines = []
    for s in report.samples:
        published = s.published_at.isoformat() if s.published_at else "발행일 없음"
        if s.failure is not None:
            state = f"{'차단' if s.blocked else '실패'} — {s.failure}"
        elif s.paywalled:
            state = "유료"
        else:
            state = f"본문 {s.via} {s.body_length}자"
        author = "저자 있음" if s.author else "저자 없음"
        lines.append(f"{s.article_id}  {published}  {state}  {author}  {s.url}")
    if report.page2_line:
        lines.append(f"{report.page2_line} → {report.page2}")
    return lines


def summary_row(report: Report) -> str:
    dates = [c.published_at for c in report.page1 if c.published_at]
    span = f"{(max(dates) - min(dates)).total_seconds() / 86400:.1f}" if dates else "-"
    fetched = [s for s in report.samples if s.failure is None]
    lengths = [s.body_length for s in fetched if not s.paywalled]
    n = len(report.samples)
    cells = [
        report.key,
        report.country,
        report.format,
        str(len(report.page1)),
        span,
        ",".join(_path(s) for s in report.samples) or "-",
        str(int(statistics.median(lengths))) if lengths else "-",
        f"{sum(s.paywalled for s in report.samples)}/{n}",
        f"{sum(s.blocked for s in report.samples)}/{n}",
        f"{sum(s.author for s in fetched)}/{n}",
        report.page2 or "-",
        report.end or "-",
    ]
    return "| " + " | ".join(cells) + " |"


def _path(sample: Sample) -> str:
    if sample.blocked:
        return "차단"
    if sample.failure is not None:
        return "실패"
    if sample.paywalled:
        return "유료"
    return sample.via or "없음"
