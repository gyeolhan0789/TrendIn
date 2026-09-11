"""ingest — Kafka `raw-file-ready` 를 소비해 정제하고 `curated`·`contents` 에 쓴다 ([02]·[03]).

모양은 `trendin.spark.dag_factory` 에 있고 여기는 설정만 든다 (README 규약 1).

**도메인별로 나누지 않는다.** 토픽이 하나이고 도메인은 이벤트 안에 있다 ([02 §1]).

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**시간 단위로 도는 이유**는 `collect` 가 그렇기 때문이다 (fashion 매시 · dev 30분). 정각에
수집이 시작되므로 :30 에 받는다 — 수집이 끝나기 전에 돌아도 손해는 없다(다음 회차가 마저
받는다). 다만 **7일 안에는 반드시 한 번 돌아야 한다** — Kafka 보존이 168시간이라 그보다 오래
안 돌면 그 사이 이벤트를 영영 못 받는다. MinIO 객체는 남으므로 [02 §6] 의 `--source objects`
로 복구는 되지만 그건 수동 백필이다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import CURATED, build_spark_dag

spark_ingest = build_spark_dag(
    dag_id="spark_ingest",
    schedule="30 * * * *",
    job="ingest",
    # `Trigger.AvailableNow` 라 쌓인 것을 다 먹고 스스로 끝난다 ([01 §1]). 그래도 상한을
    # 둔다 — 안 두면 죽은 실행이 `max_active_runs=1` 을 붙잡아 다음 회차가 영영 안 돈다.
    execution_timeout=timedelta(hours=2),
    outlets=[CURATED],
    doc_md=__doc__,
)
