"""analyze — 집계가 끝난 24H/7D/30D 트렌드를 분석해 `trend_analyses`에 저장한다.

세 기간을 기본 실행한다. 단일 기간 확인에는 Job의 `--period`를 사용한다.

⚠️ Airflow 안전 모드가 이 파일을 찾도록 문서에 `airflow`와 `dag`를 함께 둔다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import METRICS, build_spark_dag

spark_analyze = build_spark_dag(
    dag_id="spark_analyze",
    schedule=[METRICS],
    job="analyze",
    execution_timeout=timedelta(hours=2),
    doc_md=__doc__,
)
