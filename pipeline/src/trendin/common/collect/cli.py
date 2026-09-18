"""백필 명령들이 같이 쓰는 인자 파서."""

from __future__ import annotations

import argparse
from datetime import datetime


def offset_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(f"오프셋이 없다 — KST 면 +09:00 을 붙인다: {value!r}")
    return parsed
