"""extract — `curated` 를 읽어 키워드 후보를 뽑고 승격까지 간다 ([04]·[05]).

**`ingest` 가 성공했을 때만 돈다.** 크론 간격이 아니라 자산(`CURATED`)으로 잇는다 — `ingest`
가 몇 분 걸리는지 모르는 채로 시각을 박으면 느린 회차에서 빈손으로 돈다.

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**도메인별 태스크로 나눈다.** 세 Job 중 도메인을 아는 것은 이것뿐이고([04 §8] 도메인별 옵션),
한 도메인의 코퍼스가 깨져도 다른 도메인은 도는 편이 낫다.

🚫 **승격은 백엔드에 막혀 있다.** `keywords (domain, normalized_name)` UNIQUE 가 없으면
([08 §5] 티어 1) 승격만 건너뛰고 나머지는 돈다. 그 상태에서는 `aggregate` 가 0행을 낸다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import CURATED, KEYWORDS, build_spark_dag

spark_extract = build_spark_dag(
    dag_id="spark_extract",
    schedule=[CURATED],
    job="extract",
    task_args={
        "fashion": ("--domain", "fashion"),
        "dev": ("--domain", "dev"),
    },
    execution_timeout=timedelta(hours=2),
    outlets=[KEYWORDS],
    doc_md=__doc__,
)
