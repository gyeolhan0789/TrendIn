"""과거분 백필 CLI (S15P21A102-163, 상한과 거부는 S15P21A102-204).

백필이 주기 실행과 갈리는 지점 둘을 겨눈다 — 어떤 소스를 받아 주나, 어디서 멈추나.
"""

import pytest

from trendin.fashion.collect import backfill


def test_목록_소스는_받지_않는다():
    """RssAdapter 를 붙이면 HTML 을 피드로 파싱해 0 건을 내고 성공으로 끝난다.

    목록 소스에 과거분이 없다는 건 `ListingAdapter.discover(page=...)` 가 이미 거부하는
    사실이다. CLI 가 그걸 모르고 받으면 조용한 실패가 된다.
    """
    for key in ("cosmopolitan", "harpersbazaar"):
        with pytest.raises(SystemExit) as exc:
            backfill.main([key, "--pages", "3"])
        assert "목록" in str(exc.value)


def test_rss_소스는_받는다():
    """거부가 route 로 갈리는지 본다. 파싱까지 가지 않고 인자 검사에서 갈린다."""
    assert set(backfill.BACKFILLABLE) == {"allure", "gqkorea", "marieclaire", "vogue", "wkorea"}


def test_페이지가_전부_이미_받은_기사면_멈춘다():
    """이미 다 받은 소스에 다시 돌려도 `--pages` 만큼 목록을 치지 않는다."""
    seen = []

    class Adapter:
        def __init__(self, source, session):
            self.source = source

        def discover(self, page=None):
            seen.append(page)
            return _result([f"a{page}"])

    ledger = _AllKnownLedger()
    backfill.walk_pages(Adapter(None, None), pages=5, first_page=2, ledger=ledger, store=None)
    assert seen == [2], f"첫 페이지가 전부 아는 기사면 멈춘다 — 실제로 친 페이지: {seen}"


def test_장부가_없으면_멈추지_않는다():
    """훑기 모드(`--store` 없음)는 진단용이라 이미 받은 기사도 보여야 한다."""
    seen = []

    class Adapter:
        def __init__(self):
            self.source = None

        def discover(self, page=None):
            seen.append(page)
            return _result([f"a{page}"])

        def materialize(self, candidate):
            return b"", None

    backfill.walk_pages(Adapter(), pages=3, first_page=2, ledger=None, store=None)
    assert seen == [2, 3, 4]


class _AllKnownLedger:
    def filter_new(self, source, article_ids):
        return set()


def _result(ids):
    class R:
        not_modified = False
        candidates = [type("C", (), {"article_id": i})() for i in ids]
        failures = []

    return R()
