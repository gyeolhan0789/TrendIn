"""기사 정식 URL 다듬기. 도메인을 모르는 규칙이라 어댑터들이 같이 쓴다 (article.json `url`)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = frozenset({"fbclid", "gclid"})


def clean_url(url: str) -> str:
    """추적 파라미터만 뺀다. percent-encoding 은 소스가 발행한 정식 URL 이라 그대로 둔다."""
    parts = urlsplit(url)
    if not parts.query:
        return url
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith(TRACKING_PREFIXES) and key not in TRACKING_KEYS
    ]
    return urlunsplit(parts._replace(query=urlencode(kept)))
