"""concept — 승격된 키워드를 언어 무관 개념 번호에 붙인다 (`src/trendin/spark/concept/`).

**`extract` 가 승격을 끝냈을 때만 돈다.** 자산(`KEYWORDS`)으로 잇는다 — 붙일 대상이 승격된
키워드라서, 승격이 안 돌았으면 이 Job 은 빈손이다.

**도메인 인자를 받는다.** 개념 표는 지금 패션만 있다. dev 도메인은 초기 사전이 없어 전부 미등록으로
쌓일 뿐이라 태스크를 만들지 않는다 — 초기 사전이 생기면 `task_args` 에 한 줄 더한다.

**LLM 을 부르지 않는다.** 사전에 있는 것만 붙이고 없는 것은 `pl_unmapped_expression` 에 쌓는다.
쌓인 것을 검수 명령(`scripts/concept-review.py`)으로 처리하면 다음 실행이 반영한다.

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**선행 조건이 없다.** 개념 표 넷도 `pl_` 표라 Job 이 처음 돌 때 자기가 만든다 — 스프링이 읽지
않으므로 Flyway 를 거치지 않는다 (2026-09-17). 초기 사전도 Job 이 매 실행 앞에서 저장소 파일에서
반영하므로, 켜기 전에 사람이 할 일이 없다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import KEYWORDS, build_spark_dag

spark_concept = build_spark_dag(
    dag_id="spark_concept",
    schedule=[KEYWORDS],
    job="concept",
    task_args={
        "fashion": ("--domain", "fashion"),
    },
    execution_timeout=timedelta(minutes=30),
    doc_md=__doc__,
)
