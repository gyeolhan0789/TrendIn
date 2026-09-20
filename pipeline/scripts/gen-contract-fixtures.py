#!/usr/bin/env python
"""계약 fixture 생성 (S15P21A102-159).

`spark/tests/fixtures/contract/` 를 만든다. 소비 측(169)이 저장소 없이 파싱·검증 코드를
돌리는 근거다. 계약 설명은 `docs/spark-integration.md`.

**손으로 쓰지 않고 이 스크립트로 만드는 이유** — `checksum` 은 `article.json` 바이트의
sha256 이고, 봉투의 값은 `article.json` 의 값과 같아야 한다. 손으로 맞추면 틀리고, 틀린
fixture 는 없는 fixture 보다 나쁘다. 소비 측이 그 모양대로 짜고 실제 토픽에서 터진다.

```sh
cd pipeline
.venv/bin/python scripts/gen-contract-fixtures.py     # scripts/dev-setup.sh 를 먼저 한 번
.venv/bin/pytest tests/common/test_contract_fixtures.py
```

샘플 값은 `tests/common/test_events.py` 의 `ledger_row()` 와 같게 둔다. 두 곳이 갈리면 같은
계약을 두 모양으로 설명하는 셈이 된다.

**요약 이벤트는 만들지 않는다.** 브로커와 함께 걷혔다 (Kafka 제거 3/3). 같은 폴더의
`run-summary-*.json` 은 토픽 분리 전 봉투의 기록이고 소비 측 판별기 테스트가 그대로 쓴다 —
생산자가 없으므로 이 스크립트도, `test_contract_fixtures.py` 도 그것을 만들거나 대조하지
않는다.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trendin.common.collect.article import Article
from trendin.common.collect.events import article_event
from trendin.common.collect.flow import article_bytes
from trendin.common.collect.keys import article_key, raw_key
from trendin.common.collect.ledger import LedgerRow

KST = timezone(timedelta(hours=9), "KST")
BUCKET = "raw-data"

PIPELINE = Path(__file__).resolve().parents[1]
OUT = PIPELINE / "spark" / "tests" / "fixtures" / "contract"

DOMAIN = "fashion"
SOURCE = "vogue"
# 두산매거진이 한국에서 발행한다 (`trendin.fashion.collect.sources`).
SOURCE_COUNTRY = "KR"
ROUTE = "rss"
ARTICLE_ID = "854414"
URL = "https://www.vogue.co.kr/2026/09/03/some-article/"
TITLE = "2026 F/W 런웨이가 다시 꺼낸 실루엣"
PUBLISHED_AT = datetime(2026, 9, 3, 10, 0, tzinfo=KST)
COLLECTED_AT = datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc)

# 발급이 있던 시절의 실행 식별자. 봉투가 그 칸을 들고 있어 견본도 값을 들고 있다.
RUN_ID = "20260903T100000"

SYNTHETIC_SUMMARY = "이 문단은 fixture 용 합성 요약이다. 실제 기사 문장이 아니다."
SYNTHETIC_BODY = (
    "이 문단은 fixture 용 합성 본문이다. 실제 기사 문장이 아니다.\n"
    "정제 단계가 HTML 을 벗기고 문장을 나누는 동작을 확인할 수 있을 만큼만 길게 둔다."
)

# 피드 소스의 raw 는 받은 item 조각이다 (`contracts.Candidate.raw`).
#
# 본문이 합성 문장인 이유는 저작권이다. 실제 기사 본문을 fixture 에 넣으면 fixture 자체가
# 복제물이 되고, 그건 Git 에 영구히 남는다 — MinIO 원문은 90일 만료가 걸리지만(불변식 13)
# 리포지토리에는 그런 것이 없다.
RAW_XML = """<?xml version="1.0" encoding="UTF-8"?>
<item>
  <title>2026 F/W 런웨이가 다시 꺼낸 실루엣</title>
  <link>https://www.vogue.co.kr/2026/09/03/some-article/</link>
  <guid isPermaLink="false">https://www.vogue.co.kr/?p=854414</guid>
  <pubDate>Thu, 03 Sep 2026 01:00:00 +0000</pubDate>
  <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">홍길동</dc:creator>
  <category>fashion</category>
  <category>runway</category>
  <description>이 문단은 fixture 용 합성 요약이다. 실제 기사 문장이 아니다.</description>
  <content:encoded xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <![CDATA[<p>이 문단은 fixture 용 합성 본문이다. 실제 기사 문장이 아니다.</p>
    <p>정제 단계가 HTML 을 벗기고 문장을 나누는 동작을 확인할 수 있을 만큼만 길게 둔다.</p>]]>
  </content:encoded>
</item>
"""


def build() -> tuple[dict[str, dict], dict[str, bytes]]:
    """기사 이벤트 하나와 객체 둘을 만든다. 파일로 쓰기 전에 값이 전부 여기서 결정된다."""
    raw = RAW_XML.encode("utf-8")

    article = Article(
        domain=DOMAIN,
        source=SOURCE,
        route=ROUTE,
        article_id=ARTICLE_ID,
        url=URL,
        title=TITLE,
        published_at=PUBLISHED_AT,
        collected_at=COLLECTED_AT,
        raw_key=raw_key(DOMAIN, SOURCE, ROUTE, PUBLISHED_AT, ARTICLE_ID, ext="xml"),
        content_sha256=hashlib.sha256(raw).hexdigest(),
        summary=SYNTHETIC_SUMMARY,
        body_text=SYNTHETIC_BODY,
        categories=["fashion", "runway"],
        author="홍길동",
        members_only=False,
        paywalled=False,
    )
    body = article_bytes(article)

    row = LedgerRow(
        source=SOURCE,
        article_id=ARTICLE_ID,
        domain=DOMAIN,
        url=URL,
        title=TITLE,
        published_at=PUBLISHED_AT,
        collected_at=COLLECTED_AT,
        article_key=article_key(DOMAIN, SOURCE, ROUTE, PUBLISHED_AT, ARTICLE_ID),
        # 봉투의 `checksum` 은 `object_key` 가 가리키는 객체, 즉 article.json 의 해시다.
        # 장부의 `content_sha256`(raw 의 해시)과 이름만 비슷한 다른 값이다.
        article_sha256=hashlib.sha256(body).hexdigest(),
        raw_key=article.raw_key,
        members_only=False,
        paywalled=False,
    )

    events = {
        "article-event.json": article_event(
            row, bucket=BUCKET, run_id=RUN_ID, source_country=SOURCE_COUNTRY
        ),
    }
    assert article.raw_key is not None  # 이 fixture는 공개 RSS 기사다.
    objects = {row.article_key: body, article.raw_key: raw}
    return events, objects


def main() -> None:
    events, objects = build()

    for name, event in events.items():
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # 이벤트는 사람이 읽는 물건이라 들여쓴다. 어디로 흐르는 바이트가 아니므로
        # 포매팅이 계약에 영향을 주지 않는다.
        path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {path.relative_to(PIPELINE)}")

    for key, body in objects.items():
        path = OUT / "objects" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        # 객체는 바이트 그대로 쓴다. 다시 포매팅하면 checksum 이 깨진다.
        path.write_bytes(body)
        print(f"  {path.relative_to(PIPELINE)}")

    article = events["article-event.json"]
    body = objects[article["object_key"]]
    assert article["checksum"] == "sha256-" + hashlib.sha256(body).hexdigest()
    print()
    print("검사는 tests/common/test_contract_fixtures.py 가 한다.")


if __name__ == "__main__":
    main()
