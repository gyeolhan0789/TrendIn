"""환경변수 하나를 꺼내는 자리.

접속값은 전부 환경변수로 온다(`pipeline/README.md` 규약 10 — UI 에서 Connection·Variable 을
만들지 않는다). 빈 값을 그대로 들고 내려가면 boto3·psycopg2 안쪽에서 엉뚱한 오류가 나므로
꺼내는 자리에서 끊는다.
"""

from __future__ import annotations

import os


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} 이 비어 있다. pipeline/.env 를 채운다")
    return value
