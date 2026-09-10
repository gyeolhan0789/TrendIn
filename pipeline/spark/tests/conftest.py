"""Spark 테스트 공통 설정.

`spark/jobs/*.py` 는 `spark-submit` 이 파일 경로로 실행하는 스크립트라 패키지가 아니다.
테스트에서 그대로 import 할 수 있게 경로만 덧붙인다 — 이렇게 해두면 진입점이 깨졌을 때
`spark-submit` 을 돌리기 전에 잡힌다.

이 디렉터리도 함께 넣는다. `registry_support.py` 처럼 여러 시험이 나눠 쓰는 헬퍼를
`conftest.py` 에 두면 층 2 의 `tests/spark/conftest.py` 와 이름이 충돌한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS_DIR = HERE.parent / "jobs"

for directory in (JOBS_DIR, HERE):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

