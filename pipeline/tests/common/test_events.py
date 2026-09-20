"""기사 이벤트 봉투 (설계 문서 #6, 팀 계약 `docs/data-pipeline-design.md` 5장).

`events.article_event()` 는 이제 아무것도 발행하지 않는다 (Kafka 제거 3/3). 봉투의 정본
으로 남아 `collected_article_event` 뷰와 소비 측 fixture 가 그것을 흉내 낸다. 여기서
지키는 것은 그 정본이 내는 칸과 값이다.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trendin.common.collect.events import article_event
from trendin.common.collect.ledger import LedgerRow

KST = timezone(timedelta(hours=9))

RUN_ID = "20260903T110000"

CONTRACT = Path(__file__).resolve().parents[2] / "spark" / "docs" / "02-input-contract.md"


def _event_schema_fields() -> dict[str, bool]:
    """소비 계약의 `EVENT_SCHEMA` 선언에서 {필드: nullable} 을 읽는다.

    **`_` 로 시작하는 칸은 뺀다.** 그 스키마는 소비 측 리더의 컬럼 목록이라 Spark 가
    채우는 칸도 들어 있다 — `_corrupt_record` 는 PERMISSIVE 모드가 파싱 실패 원문을
    담는 자리다(`02 §1`, `spark/io/schema.py` 의 `CORRUPT_FIELD`). 생산자가 채울 값이
    아니므로 봉투 계약 밖이고, 개별 이름이 아니라 접두어로 걸러 리더 칸이 하나 더 늘어도
    이 테스트가 생산자를 잘못 고발하지 않게 한다.
    """
    text = CONTRACT.read_text(encoding="utf-8")
    block = re.search(r"EVENT_SCHEMA = StructType\(\[(.+?)\]\)", text, re.S)
    assert block, f"{CONTRACT} 에서 EVENT_SCHEMA 를 못 찾았다"
    rows = re.findall(r'StructField\("(\w+)",\s*\w+\(\),\s*(True|False)\)', block.group(1))
    assert rows, "EVENT_SCHEMA 안에서 StructField 를 못 찾았다"
    return {name: flag == "True" for name, flag in rows if not name.startswith("_")}


def ledger_row(**over) -> LedgerRow:
    base = dict(
        source="vogue",
        article_id="854414",
        domain="fashion",
        url="https://www.vogue.co.kr/2026/09/03/some-article/",
        title="제목",
        published_at=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        collected_at=datetime(2026, 9, 3, 2, 10, tzinfo=timezone.utc),
        article_key="fashion/vogue/rss/2026/09/03/854414/article.json",
        article_sha256="a" * 64,
        raw_key="fashion/vogue/rss/2026/09/03/854414/raw.xml",
        members_only=False,
        paywalled=False,
    )
    base.update(over)
    return LedgerRow(**base)


def test_기사_이벤트는_event_id_가_기사마다_다르다():
    """팀 봉투의 `{source_id}-{run_id}` 를 그대로 쓰면 한 실행의 기사들이 전부 같아진다."""
    a = article_event(ledger_row(article_id="1"), bucket="raw-data", run_id=RUN_ID,
                      source_country="KR")
    b = article_event(ledger_row(article_id="2"), bucket="raw-data", run_id=RUN_ID,
                      source_country="KR")
    assert a["event_id"] == "vogue-1"
    assert a["event_id"] != b["event_id"]


def test_checksum_은_article_json_의_해시고_접두어가_붙는다():
    event = article_event(ledger_row(article_sha256="b" * 64), bucket="raw-data", run_id=RUN_ID,
                          source_country="KR")
    assert event["checksum"] == "sha256-" + "b" * 64
    # 소비 측이 `object_key` 를 받아 대조하는 값이라 그 객체의 해시여야 한다.
    assert event["object_key"].endswith("article.json")


def test_collected_at_은_기사를_받은_시각이고_KST_오프셋이다():
    event = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert event["collected_at"] == "2026-09-03T11:10:00+09:00"


def test_published_at_은_소스가_준_오프셋_그대로다():
    event = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert event["published_at"] == "2026-09-03T10:00:00+09:00"


def test_소스_국가는_인자로_받은_값을_그대로_싣는다():
    """국가는 기사가 아니라 소스의 속성이라 장부 행에 없다. 그래서 `bucket` 처럼 인자다.

    판정할 수 없는 소스는 `XX` 가 들어온다 — 장부 뷰의 `coalesce(country, 'XX')` 와 같은 값이다.
    """
    event = article_event(ledger_row(source="hn"), bucket="raw-data", run_id=RUN_ID,
                          source_country="XX")
    assert event["source_country"] == "XX"


def test_출처_명시_필드가_빠지지_않는다():
    """저작권법 제37조. 공정이용은 출처 명시 면제 목록에 없다(불변식 11)."""
    event = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    for field in ("url", "source_id", "published_at"):
        assert event[field]


def test_본문은_싣지_않는다():
    """불변식 6 — 이벤트에 본문이 없고 키만 있다."""
    event = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert "body_text" not in event
    assert "summary" not in event


def test_회원_전용은_raw_키가_null_이다():
    row = ledger_row(members_only=True, raw_key=None)
    event = article_event(row, bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert event["raw_object_key"] is None
    assert event["members_only"] is True
    assert event["paywalled"] is False
    # article.json 은 있으므로 발급 자체는 된다 — 제목·URL·발행일은 남는다.
    assert event["object_key"]


def test_유료_표시는_raw_키가_null_이다():
    row = ledger_row(paywalled=True, raw_key=None)
    event = article_event(row, bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert event["raw_object_key"] is None
    assert (event["members_only"], event["paywalled"]) == (False, True)


def test_run_id_가_달라도_event_id_는_그_기사_하나다():
    """`event_id` 는 기사에서만 나온다 — `run_id` 를 섞으면 재처리가 중복이 된다."""
    event = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    assert event["run_id"] == RUN_ID
    assert event["collected_at"] == "2026-09-03T11:10:00+09:00"
    again = article_event(ledger_row(), bucket="raw-data", run_id="20260904T110000",
                          source_country="KR")
    assert event["event_id"] == again["event_id"]


def test_기사_봉투는_소비_계약의_필드를_다_채운다():
    required = _event_schema_fields()
    article = article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    for name, nullable in required.items():
        assert name in article
        if not nullable:
            assert article[name] is not None


def test_기사_봉투가_소비_측_판별을_그대로_통과한다():
    """필드 목록 대조보다 이쪽이 계약의 본체다.

    `_event_schema_fields()` 가 보는 `EVENT_SCHEMA` 는 "어떤 칸이 있나" 만 정하고, "어떤
    칸이 채워져 있어야 하나" 는 `spark/io/contract.py` 가 정한다(`02 §1` 마지막 문단).
    그래서 생산자 출력을 소비 측 판별기에 그대로 넣어 본다 — 칸이 하나 비면 여기서
    DLQ 사유가 이름과 함께 나온다.

    요약 봉투는 브로커와 함께 걷혔다 (Kafka 제거 2/3) — 이 판별기의 대상은 기사뿐이다.

    `contract.py` 는 stdlib 만 import 하므로 pyspark 없이 이 잡에서 돈다. `schema.py`
    (pyspark 의존)를 여기서 import 하지 않는 이유이기도 하다.
    """
    from trendin.spark.io.contract import EventShape, classify

    article = classify(
        article_event(ledger_row(), bucket="raw-data", run_id=RUN_ID, source_country="KR")
    )
    assert article.error_type is None, article.detail
    assert article.shape is EventShape.ARTICLE
