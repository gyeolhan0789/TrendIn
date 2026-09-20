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
    # **워커 둘로 묶는다.** 기본값 `local[*]` 은 4 CPU 서버에서 워커 넷을 띄우고, 워커마다
    # GLiNER 를 한 벌씩 올려 메모리를 넘긴다 — 2026-09-20 에 문서 925건이 `Python worker
    # exited unexpectedly (crashed)` 로 죽었다. 2026-09-17 실측에서 워커 하나가 RSS 2.3GB
    # 이고 가용이 7.3GB 라, 셋도 긴 문서에서 순간적으로 튄다.
    #
    # **손 실행에만 있던 조건을 DAG 에도 준다.** 그 전에는 사람이 기억해서 붙여야 했고,
    # 자동 실행은 문서가 적을 때만 우연히 살아 있었다. GLiNER 를 올리는 Job 은 이것뿐이라
    # 다른 DAG 은 그대로 둔다.
    env={"SPARK_MASTER": "local[2]"},
    execution_timeout=timedelta(hours=2),
    outlets=[KEYWORDS],
    doc_md=__doc__,
)
