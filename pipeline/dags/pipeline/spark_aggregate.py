"""aggregate — 일별 원자료로 지표·추이·트렌드 유형을 낸다 ([07]).

**여기만 자산이 아니라 시각에 걸린다.** 기준일 D 가 KST 자정으로 끊기고([07 §4]) 백엔드가
자기 시계로 같은 구간을 계산해 **등호로** 조회한다 (`AnalysisWindow.completed`). 자정 직후에
돌지 않으면 그날 목록이 **빈다** — 값이 틀리는 것이 아니라 아무것도 안 나온다.

`00:10 KST` 는 자정을 막 넘긴 뒤이면서 `spark_extract` 의 `00:30` 회차와 겹치지 않는 자리다.
겹쳐도 정확성 문제는 없다 — 원자료를 읽기만 하고 멱등하다 ([07 §7]).

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**도메인 인자가 없다.** 원자료 전체를 한 번에 본다.

재계산은 소급 구간 W(30일)가 매 실행 덮으므로([07 §2]) 하루 걸러도 다음 실행이 메운다.
백필 보정처럼 D 를 과거로 옮기는 것은 `--reaggregate` 로 손으로 돌린다 ([07 §7]).
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import METRICS, build_spark_dag

spark_aggregate = build_spark_dag(
    dag_id="spark_aggregate",
    schedule="10 0 * * *",
    job="aggregate",
    execution_timeout=timedelta(hours=1),
    outlets=[METRICS],
    doc_md=__doc__,
)
