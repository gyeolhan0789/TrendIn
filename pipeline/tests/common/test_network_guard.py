"""테스트 공용 네트워크 막음 (`tests/conftest.py` 의 `_no_real_http`)."""

import pytest

from trendin.common.collect.session import CollectSession


def test_전송을_끼우지_않은_세션은_실제_요청_전에_실패한다():
    with CollectSession(
        allowed_url_prefixes=("https://example.test/",), sleep=lambda _s: None
    ) as s:
        with pytest.raises(AssertionError, match="실제 네트워크"):
            s.get("https://example.test/feed/")
