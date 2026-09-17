"""소스 프로필 로더 (`source-discovery.md` #3, S15P21A102-284).

CI 가 모든 프로필을 여기서 읽는다(확정 8). 런타임에는 깨진 프로필 하나가 DAG 전체를
멈추므로, 그 전에 머지를 막는 자리가 이 시험이다.
"""

import datetime as dt
from pathlib import Path

import pytest

from trendin.common.collect.contracts import License, Rule
from trendin.common.collect.profiles import ProfileError, load_profiles
from trendin.fashion.collect import sources

FASHION = Path(sources.__file__).parent

VALID = """\
key = "sample"
domain = "fashion"
route = "rss"
country = "JP"
discover_url = "https://example.test/feed/"
allowed_url_prefixes = ["https://example.test/"]
article_id = { rule = "guid_query_param", param = "p" }
published_at = { rule = "rss_pubdate" }
"""


def with_id(rule: str) -> str:
    return VALID.replace('rule = "guid_query_param", param = "p"', rule)


def write(tmp_path: Path, text: str, key: str = "sample") -> Path:
    (tmp_path / f"{key}.toml").write_text(text, encoding="utf-8")
    return tmp_path


def load_one(tmp_path: Path, text: str, key: str = "sample"):
    (source,) = load_profiles(write(tmp_path, text, key), domain="fashion")
    return source


def test_레포의_패션_프로필이_전부_읽힌다():
    loaded = load_profiles(FASHION, domain="fashion")
    assert [s.key for s in loaded] == sorted(p.stem for p in FASHION.glob("*.toml"))
    assert loaded == sources.RSS_SOURCES


def test_프로필이_SourceDef_가_된다(tmp_path):
    source = load_one(
        tmp_path,
        VALID
        + 'page_param = "paged"\n'
        + 'license = { name = "CC BY 4.0", url = "https://example.test/license", '
        + "reviewed_on = 2026-09-17 }\n",
    )
    assert source.key == "sample"
    assert source.country == "JP"
    assert source.allowed_url_prefixes == ("https://example.test/",)
    assert source.article_id == Rule("guid_query_param", "p")
    assert source.published_at == Rule("rss_pubdate")
    assert source.page_param == "paged"
    assert source.license == License(
        "CC BY 4.0", "https://example.test/license", dt.date(2026, 9, 17)
    )


@pytest.mark.parametrize(
    ("article_id", "published_at"),
    [
        ('{ rule = "guid_hash" }', '{ rule = "atom_published" }'),
        ('{ rule = "guid_hash" }', '{ rule = "atom_updated" }'),
        ('{ rule = "guid_query_param", param = "post" }', '{ rule = "dc_date" }'),
        ('{ rule = "url_path_segment", param = -2 }', '{ rule = "rss_pubdate" }'),
    ],
)
def test_피드_규칙_열거형을_받는다(tmp_path, article_id, published_at):
    text = VALID.replace('{ rule = "guid_query_param", param = "p" }', article_id).replace(
        '{ rule = "rss_pubdate" }', published_at
    )
    source = load_one(tmp_path, text)
    assert source.article_id.name in article_id
    assert source.published_at.name in published_at


def test_선택_칸이_없으면_페이지_넘김도_라이선스도_없다(tmp_path):
    source = load_one(tmp_path, VALID)
    assert source.page_param is None
    assert source.license is None


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (VALID + 'guid_param = "p"\n', "모르는 키"),
        (VALID + 'author_field = "author"\n', "모르는 키"),
        (VALID.replace('country = "JP"\n', ""), "필수 칸이 없다: country"),
        (VALID.replace('"JP"', '"jp"'), "country"),
        (VALID.replace('"JP"', '"US/UK"'), "country"),
        (VALID.replace('key = "sample"', 'key = "other"'), "파일 이름"),
        (VALID.replace('domain = "fashion"', 'domain = "dev"'), "domain"),
        (VALID.replace('route = "rss"', 'route = "listing"'), "route"),
        (VALID.replace('["https://example.test/"]', "[]"), "allowed_url_prefixes"),
        (VALID.replace('["https://example.test/"]', '["http://example.test/"]'), "https://"),
        (VALID.replace("https://example.test/feed/", "https://other.test/feed/"), "허용 범위 밖"),
        (VALID.replace('rule = "guid_query_param", param = "p"', 'rule = "regex"'), "article_id"),
        (VALID.replace(', param = "p"', ""), "param 이 있어야"),
        (with_id('rule = "guid_query_param", param = 1'), "문자열"),
        (with_id('rule = "url_path_segment", param = "-2"'), "정수"),
        (with_id('rule = "url_path_segment", param = true'), "정수"),
        (VALID.replace('{ rule = "rss_pubdate" }', '{ rule = "rss_pubdate", param = "x" }'),
         "param 을 받지 않는다"),
        (VALID.replace('{ rule = "rss_pubdate" }', '"rss_pubdate"'), "표여야"),
        (VALID.replace('{ rule = "rss_pubdate" }', '{ rule = "meta_property" }'), "published_at"),
        (VALID + 'page_param = ""\n', "page_param"),
        (VALID + 'license = { name = "CC BY 4.0" }\n', "license"),
        (VALID + 'license = { name = "a", url = "b", reviewed_on = "2026-09-17" }\n', "날짜"),
        ("key = ", "sample.toml"),
    ],
)
def test_깨진_프로필은_이유를_달고_실패한다(tmp_path, text, reason):
    with pytest.raises(ProfileError, match=reason):
        load_one(tmp_path, text)


def test_하나라도_깨지면_전부_실패하고_깨진_파일을_모두_알린다(tmp_path):
    """깨진 파일만 건너뛰면 그 소스가 조용히 빠진 채 돈다 (확정 8)."""
    write(tmp_path, VALID, "sample")
    write(tmp_path, VALID.replace('key = "sample"', 'key = "a"').replace('"JP"', '"jpn"'), "a")
    write(tmp_path, VALID.replace('key = "sample"', 'key = "b"') + "extra = 1\n", "b")
    with pytest.raises(ProfileError) as caught:
        load_profiles(tmp_path, domain="fashion")
    assert "a.toml" in str(caught.value)
    assert "b.toml" in str(caught.value)
    assert "sample.toml" not in str(caught.value)
