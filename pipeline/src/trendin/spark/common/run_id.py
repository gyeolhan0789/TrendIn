"""Job 실행 식별자 — `ingest_run_id` · `extract_run_id` 의 형식 ([01 §3]).

생산자의 `run_id` 와 형식(`yyyyMMddTHHmmss`)은 같고 뜻이 다르다 — 그쪽은 수집기가 한 번 돈
것이고 이쪽은 이 Job 이 한 번 돈 것이다. KST 인 이유는 `curated` 파티션의 `published_date` 가
KST 이고(불변식 10) 둘을 나란히 읽을 때 시간대가 갈리면 사람이 헷갈리기 때문이다.

`spark/jobs/ingest.py` 가 같은 정의를 자기 안에 들고 있다 — `jobs/` 는 패키지가 아니라 서로
import 하지 못해서다. 형식을 바꾸면 그쪽도 함께 바꾼다.
"""

from __future__ import annotations

from datetime import datetime

from trendin.spark.normalize.documents import KST

RUN_ID_FORMAT = "%Y%m%dT%H%M%S"


def default_run_id(now: datetime | None = None) -> str:
    """지금 시각(KST). Airflow 는 logical date 를 `--run-id` 로 넘긴다 ([01 §3])."""
    moment = now or datetime.now(KST)
    return moment.astimezone(KST).strftime(RUN_ID_FORMAT)
