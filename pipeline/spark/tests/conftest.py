"""Spark 테스트 공통 설정.

`spark/jobs/*.py` 는 `spark-submit` 이 파일 경로로 실행하는 스크립트라 패키지가 아니다.
테스트에서 그대로 import 할 수 있게 경로만 덧붙인다 — 이렇게 해두면 진입점이 깨졌을 때
`spark-submit` 을 돌리기 전에 잡힌다.
"""

from __future__ import annotations

import sys
from pathlib import Path

JOBS_DIR = Path(__file__).resolve().parents[1] / "jobs"

if str(JOBS_DIR) not in sys.path:
    sys.path.insert(0, str(JOBS_DIR))
