"""article.json 모델 (설계 문서 #5.3, 불변식 9)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from trendin.common.collect.article import Article

UTC = timezone.utc
KST = timezone(timedelta(hours=9))

FULL = {
    "domain": "fashion",
    "source": "vogue",
    "route": "rss",
    "article_id": "857991",
    "url": "https://www.vogue.co.kr/2026/09/03/x/",
    "title": "제목",
    "published_at": datetime(2026, 9, 3, 4, 41, 17, tzinfo=UTC),
    "collected_at": datetime(2026, 9, 3, 5, 0, tzinfo=UTC),
    "raw_key": "fashion/vogue/rss/2026/09/03/857991/raw.xml",
    "content_sha256": "0" * 64,
}

REQUIRED = sorted(FULL)


def test_필수_필드만으로_만들어진다():
    article = Article(**FULL)
    assert article.schema_version == 1
    assert article.categories == []
    assert article.body_text is None


@pytest.mark.parametrize("missing", REQUIRED)
def test_필수_필드가_빠지면_실패한다(missing):
    with pytest.raises(ValidationError):
        Article(**{k: v for k, v in FULL.items() if k != missing})


@pytest.mark.parametrize("blank", [k for k in REQUIRED if isinstance(FULL[k], str)])
def test_필수_필드가_공백뿐이어도_비었다고_본다(blank):
    with pytest.raises(ValidationError):
        Article(**{**FULL, blank: "   "})


def test_published_at_은_소스_오프셋을_그대로_둔다():
    article = Article(**{**FULL, "published_at": datetime(2026, 9, 3, 13, 41, 17, tzinfo=KST)})
    assert article.published_at.utcoffset() == timedelta(hours=9)


def test_오프셋_없는_시각은_받지_않는다():
    with pytest.raises(ValidationError):
        Article(**{**FULL, "published_at": datetime(2026, 9, 3)})
    with pytest.raises(ValidationError):
        Article(**{**FULL, "collected_at": datetime(2026, 9, 3)})


def test_collected_at_은_UTC_로_모은다():
    article = Article(**{**FULL, "collected_at": datetime(2026, 9, 3, 14, 0, tzinfo=KST)})
    assert article.collected_at == datetime(2026, 9, 3, 5, 0, tzinfo=UTC)


def test_모르는_필드는_받지_않는다():
    with pytest.raises(ValidationError):
        Article(**{**FULL, "bodyText": "오타"})


def test_JSON_으로_낼_때_빈_선택_필드는_빠진다():
    dumped = Article(**FULL).to_json_dict()
    assert "body_text" not in dumped
    assert dumped["published_at"].startswith("2026-09-03T04:41:17")
    assert dumped["schema_version"] == 1
