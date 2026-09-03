"""사람이 눈으로 대조하는 명령.

    python -m trendin.fashion.collect.probe vogue
    python -m trendin.fashion.collect.probe vogue --json

스토리 완료 조건이 "저장 샘플을 열어 제목·발행일·본문이 원문과 맞다" 라서, 기본 출력은
훑을 수 있는 표다. 저장·발급을 하지 않고 stdout 에만 쓴다.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from trendin.common.collect.session import CollectSession
from trendin.common.collect.stores import InMemoryValidatorStore
from trendin.fashion.collect import sources
from trendin.fashion.collect.rss import RssAdapter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="probe", description=__doc__)
    parser.add_argument("source", choices=sorted(sources.BY_KEY), help="소스 키")
    parser.add_argument("--json", action="store_true", help="article.json 전문을 JSON Lines 로")
    parser.add_argument("--page", type=int, default=None, help="`?paged=N`. 기본은 파라미터 없음")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    source = sources.get(args.source)
    with CollectSession(
        allowed_url_prefixes=source.allowed_url_prefixes,
        validators=InMemoryValidatorStore(),
    ) as session:
        adapter = RssAdapter(source, session)
        result = adapter.discover(page=args.page)
        if result.not_modified:
            print("304 — 피드가 안 바뀌었다")
            return 0

        rows = []
        failed = [(f.ref, f.reason) for f in result.failures]
        for candidate in result.candidates:
            try:
                _raw, article = adapter.materialize(candidate)
            except Exception as exc:  # 한 건이 실패해도 나머지는 간다
                failed.append((candidate.article_id, str(exc)))
                continue
            if args.json:
                print(json.dumps(article.to_json_dict(), ensure_ascii=False))
            else:
                rows.append(article)

        if not args.json:
            _print_table(rows)
        for ref, reason in failed:
            print(f"  실패 {ref}: {reason}", file=sys.stderr)
    return 0


def _print_table(articles: list) -> None:
    print(f"{'article_id':>10}  {'발행일(KST)':<17}  {'본문':>6}  제목")
    for article in articles:
        head = (article.body_text or "").replace("\n", " ")[:80]
        published = article.published_at.astimezone().strftime("%Y-%m-%d %H:%M")
        print(
            f"{article.article_id:>10}  {published:<17}  "
            f"{len(article.body_text or ''):>6}  {article.title[:50]}"
        )
        print(f"{'':>10}  {article.url}")
        if head:
            print(f"{'':>10}  {head}…")


if __name__ == "__main__":
    raise SystemExit(main())
