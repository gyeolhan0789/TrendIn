"""로깅 설정. 사람이 읽는 줄은 파이썬 쪽, JVM 쪽은 log4j 가 찍는다."""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-5s %(name)s — %(message)s"
_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """루트 로거를 한 번만 세운다. `spark-submit` 이 두 번 부르는 경우가 있다."""
    global _CONFIGURED
    resolved = getattr(logging, level.upper(), logging.INFO)
    if _CONFIGURED:
        logging.getLogger().setLevel(resolved)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(resolved)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
