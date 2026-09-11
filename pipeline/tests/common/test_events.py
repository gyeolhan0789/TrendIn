"""이벤트 봉투 (설계 문서 #6, 팀 계약 `docs/data-pipeline-design.md` 5장).

봉투가 두 모양이라 소비 측이 `object_key` 로 가른다는 것, 그리고 배치용 필드가 기사 단위로
어떻게 재해석되는지가 여기서 갈린다.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trendin.common.collect.events import article_event, run_summary_event
from trendin.common.collect.ledger import PendingArticle

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


def pending(**over) -> PendingArticle:
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
    )
    base.update(over)
    return PendingArticle(**base)


def test_기사_이벤트는_event_id_가_기사마다_다르다():
    """팀 봉투의 `{source_id}-{run_id}` 를 그대로 쓰면 한 실행의 기사들이 전부 같아진다."""
    a = article_event(pending(article_id="1"), bucket="raw-data", run_id=RUN_ID)
    b = article_event(pending(article_id="2"), bucket="raw-data", run_id=RUN_ID)
    assert a["event_id"] == "vogue-1"
    assert a["event_id"] != b["event_id"]


def test_checksum_은_article_json_의_해시고_접두어가_붙는다():
    event = article_event(pending(article_sha256="b" * 64), bucket="raw-data", run_id=RUN_ID)
    assert event["checksum"] == "sha256-" + "b" * 64
    # 소비 측이 `object_key` 를 받아 대조하는 값이라 그 객체의 해시여야 한다.
    assert event["object_key"].endswith("article.json")


def test_collected_at_은_기사를_받은_시각이고_KST_오프셋이다():
    event = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    assert event["collected_at"] == "2026-09-03T11:10:00+09:00"


def test_published_at_은_소스가_준_오프셋_그대로다():
    event = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    assert event["published_at"] == "2026-09-03T10:00:00+09:00"


def test_출처_명시_필드가_빠지지_않는다():
    """저작권법 제37조. 공정이용은 출처 명시 면제 목록에 없다(불변식 11)."""
    event = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    for field in ("url", "source_id", "published_at"):
        assert event[field]


def test_본문은_싣지_않는다():
    """불변식 6 — 이벤트에 본문이 없고 키만 있다."""
    event = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    assert "body_text" not in event
    assert "summary" not in event


def test_회원_전용은_raw_키가_null_이다():
    row = pending(members_only=True, raw_key=None)
    event = article_event(row, bucket="raw-data", run_id=RUN_ID)
    assert event["raw_object_key"] is None
    assert event["members_only"] is True
    # article.json 은 있으므로 발급 자체는 된다 — 제목·URL·발행일은 남는다.
    assert event["object_key"]


def test_요약_이벤트는_object_key_가_null_이라_기사_이벤트와_갈린다():
    event = run_summary_event(
        source="vogue",
        domain="fashion",
        run_id="20260903T100000",
        logical_date=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
        status="success",
        record_count=0,
        bucket="raw-data",
    )
    assert event["object_key"] is None
    assert event["event_id"] == "vogue-20260903T100000"
    assert event["record_count"] == 0  # 0건도 낸다 (팀 발행 규약 4)


def test_실패_요약은_이유를_반드시_채운다():
    """팀 발행 규약 5 — 소비 측이 누락과 실패를 구분해야 한다."""
    with pytest.raises(ValueError):
        run_summary_event(
            source="vogue",
            domain="fashion",
            run_id="20260903T100000",
            logical_date=datetime(2026, 9, 3, 10, 0, tzinfo=KST),
            status="failed",
            record_count=0,
            bucket="raw-data",
        )


def test_기사_이벤트도_run_id_를_싣는다():
    """소비 측이 `run_id` 로 curated 를 파티션하고 재처리 단위를 자른다.

    값은 **발급한 실행**이다. 수집 시각은 `collected_at` 이 따로 든다 — 두 값이 갈리는
    것이 이월분(저장은 실행 N, 발급은 실행 N+1)에서 정상이다.
    """
    event = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    assert event["run_id"] == "20260903T110000"
    # 수집 시각은 실행과 무관하게 그대로다.
    assert event["collected_at"] == "2026-09-03T11:10:00+09:00"


def test_봉투_두_모양이_소비_계약의_필드를_다_채운다():
    """계약이 요구하는 칸이 빠지면 소비 측 스키마가 그 줄을 null 로 읽는다.

    필드 목록을 여기 베끼지 않고 `02-input-contract.md` 의 `EVENT_SCHEMA` 에서 읽는다.
    베끼면 문서가 바뀌어도 이 테스트가 모른다.
    """
    required = _event_schema_fields()
    article = article_event(pending(), bucket="raw-data", run_id=RUN_ID)
    summary = run_summary_event(
        source="vogue",
        domain="fashion",
        run_id=RUN_ID,
        logical_date=datetime(2026, 9, 3, 11, 0, tzinfo=KST),
        status="success",
        record_count=3,
        bucket="raw-data",
    )
    for name, nullable in required.items():
        for label, event in (("기사", article), ("요약", summary)):
            assert name in event, f"{label} 이벤트에 {name} 이 없다"
            if not nullable:
                assert event[name] is not None, f"{label} 이벤트의 {name} 이 null 이다"


def test_봉투_두_모양이_소비_측_판별을_그대로_통과한다():
    """필드 목록 대조보다 이쪽이 계약의 본체다.

    `_event_schema_fields()` 가 보는 `EVENT_SCHEMA` 는 "어떤 칸이 있나" 만 정하고, "어떤
    칸이 채워져 있어야 하나" 는 `spark/io/contract.py` 가 정한다(`02 §1` 마지막 문단).
    그래서 생산자 출력을 소비 측 판별기에 그대로 넣어 본다 — 칸이 하나 비면 여기서
    DLQ 사유가 이름과 함께 나온다.

    `contract.py` 는 stdlib 만 import 하므로 pyspark 없이 이 잡에서 돈다. `schema.py`
    (pyspark 의존)를 여기서 import 하지 않는 이유이기도 하다.
    """
    from trendin.spark.io.contract import EventShape, classify

    article = classify(article_event(pending(), bucket="raw-data", run_id=RUN_ID))
    assert article.error_type is None, article.detail
    assert article.shape is EventShape.ARTICLE

    summary = classify(
        run_summary_event(
            source="vogue",
            domain="fashion",
            run_id=RUN_ID,
            logical_date=datetime(2026, 9, 3, 11, 0, tzinfo=KST),
            status="success",
            record_count=3,
            bucket="raw-data",
        )
    )
    assert summary.error_type is None, summary.detail
    # `object_key` 가 null 이라 요약으로 갈린다 — 계약 위반이 아니다 (02 §2).
    assert summary.shape is EventShape.SUMMARY
