"""이벤트 봉투 (설계 문서 #6, 팀 계약 `docs/data-pipeline-design.md` 5장).

봉투가 두 모양이라 소비 측이 `object_key` 로 가른다는 것, 그리고 배치용 필드가 기사 단위로
어떻게 재해석되는지가 여기서 갈린다.
"""

from datetime import datetime, timedelta, timezone

import pytest

from trendin.common.collect.events import article_event, run_summary_event
from trendin.common.collect.ledger import PendingArticle

KST = timezone(timedelta(hours=9))


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
    a = article_event(pending(article_id="1"), bucket="raw-data")
    b = article_event(pending(article_id="2"), bucket="raw-data")
    assert a["event_id"] == "vogue-1"
    assert a["event_id"] != b["event_id"]


def test_checksum_은_article_json_의_해시고_접두어가_붙는다():
    event = article_event(pending(article_sha256="b" * 64), bucket="raw-data")
    assert event["checksum"] == "sha256-" + "b" * 64
    # 소비 측이 `object_key` 를 받아 대조하는 값이라 그 객체의 해시여야 한다.
    assert event["object_key"].endswith("article.json")


def test_collected_at_은_기사를_받은_시각이고_KST_오프셋이다():
    event = article_event(pending(), bucket="raw-data")
    assert event["collected_at"] == "2026-09-03T11:10:00+09:00"


def test_published_at_은_소스가_준_오프셋_그대로다():
    event = article_event(pending(), bucket="raw-data")
    assert event["published_at"] == "2026-09-03T10:00:00+09:00"


def test_출처_명시_필드가_빠지지_않는다():
    """저작권법 제37조. 공정이용은 출처 명시 면제 목록에 없다(불변식 11)."""
    event = article_event(pending(), bucket="raw-data")
    for field in ("url", "source_id", "published_at"):
        assert event[field]


def test_본문은_싣지_않는다():
    """불변식 6 — 이벤트에 본문이 없고 키만 있다."""
    event = article_event(pending(), bucket="raw-data")
    assert "body_text" not in event
    assert "summary" not in event


def test_회원_전용은_raw_키가_null_이다():
    event = article_event(pending(members_only=True, raw_key=None), bucket="raw-data")
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
