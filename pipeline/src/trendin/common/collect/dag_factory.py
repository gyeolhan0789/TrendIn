"""수집 DAG 의 모양 하나 (S15P21A102-167).

도메인이 둘이고 실행 순서는 같다 — 스키마 확인 → 소스별 수집 → 발급. 그 순서를 DAG 파일
두 곳에 베껴 두면 한쪽만 고쳐지는 날이 온다. 그래서 모양은 여기 하나, DAG 파일은 설정만
든다(README 규약 1).

**이 모듈은 `common/collect/` 에서 유일하게 airflow 를 import 한다.** DAG 자체가 Airflow
개념이라서다. 판정은 여기 없다 — 전부 `flow.py` 에 있고 Airflow 없이 테스트된다(규약 12).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable, Sequence

import pendulum
from airflow.sdk import Asset, TriggerRule, dag, task
from airflow.sdk.exceptions import AirflowFailException

from trendin.common.collect import flow
from trendin.common.collect.contracts import ValidatorStore
from trendin.common.collect.db import Database
from trendin.common.collect.kafka_publisher import SUMMARY_TOPIC_ENV, KafkaEventPublisher
from trendin.common.collect.ledger import Ledger, PostgresLedger
from trendin.common.collect.minio_store import MinioObjectStore
from trendin.common.collect.stores import PostgresValidatorStore

logger = logging.getLogger("trendin.collect.dag")

KST = "Asia/Seoul"
COLLECT_TASK_ID = "collect_one"

# 수집 한 회차가 끝났다는 신호. `spark_ingest` 가 이것을 받아 깨어난다 (S15P21A102-247).
# 도메인 DAG 둘이 같은 자산을 내고, 소비 측은 도메인을 가리지 않으므로 어느 쪽이 끝나든
# 이어 돌면 된다 — 장부 뷰가 하나이고 도메인은 행 안에 있다.
COLLECTED = Asset("trendin://collected")

SIGNAL_TASK_ID = "signal_collected"


CollectFn = Callable[..., flow.SourceOutcome]


def build_collect_dag(
    *,
    dag_id: str,
    domain: str,
    schedule: str,
    source_keys: Sequence[str],
    domain_of: Callable[[str], str],
    collect: CollectFn | None,
    doc_md: str,
    start_date=None,
):
    """수집 DAG 하나를 만든다.

    `collect` 가 `None` 이면 그 도메인의 어댑터가 아직 없다는 뜻이다. `source_keys` 도
    비어 있어야 하고, 그러면 수집 태스크는 한 번도 실행되지 않는다(빈 매핑은 건너뛴다).
    """
    if collect is None and source_keys:
        raise ValueError(f"{dag_id}: 소스가 있는데 collect 가 없다")

    @dag(
        dag_id=dag_id,
        schedule=schedule,
        start_date=start_date or pendulum.datetime(2026, 9, 1, tz=KST),
        # 켜면 밀린 회차가 한꺼번에 돌면서 같은 사이트를 연달아 친다.
        catchup=False,
        # 겹치면 같은 호스트를 두 실행이 동시에 친다. 소스당 태스크 하나로 얻은 호스트
        # 직렬(불변식 4)은 실행이 하나일 때만 성립한다.
        max_active_runs=1,
        default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
        tags=[domain, "collect"],
        doc_md=doc_md,
    )
    def collect_dag():
        @task
        def ensure_schema() -> None:
            """장부와 validator 테이블을 멱등하게 만든다.

            앱 DB 에 마이그레이션 도구가 없어서 여기가 유일한 자동 적용 경로다.
            `collected_article` 은 JPA 밖이고 지우지 않는다 — S15P21A102-12 에 그 합의가
            적혀야 한다.
            """
            PostgresLedger(Database.from_env()).ensure_schema()

        @task(pool="crawler_pool")
        def collect_one(source_key: str) -> dict:
            """소스 하나를 발견부터 장부 기록까지. 외부 사이트를 치므로 `crawler_pool` 이다."""
            if collect is None:
                raise AirflowFailException(
                    f"{domain} 어댑터가 아직 없다 (S15P21A102-165): {source_key}"
                )
            db = Database.from_env()
            ledger: Ledger = PostgresLedger(db)
            validators: ValidatorStore = PostgresValidatorStore(db)
            try:
                outcome = collect(
                    source_key,
                    ledger=ledger,
                    store=MinioObjectStore.from_env(),
                    validators=validators,
                )
            except flow.NO_RETRY as exc:
                # 403·429 는 그 호스트를 멈춘 것이고, robots 금지·허용 범위 밖은 애초에
                # 보내면 안 되는 요청이다. 5분 뒤에 다시 보내면 불변식 1·2 를 어긴다.
                raise AirflowFailException(
                    f"{source_key}: 재시도하면 안 되는 실패 — {exc}"
                ) from exc
            return outcome.to_dict()

        @task(trigger_rule=TriggerRule.ALL_DONE)
        def publish(keys: list[str], **context) -> dict:
            """장부의 미발급 행을 전부 내고, 소스별 요약 이벤트를 낸다.

            기사 이벤트가 장부에서 나오므로 이번 실행에서 죽은 소스가 있어도, 지난 실행에서
            저장만 되고 못 나간 행이 있어도 여기서 이어 낸다(설계 문서 #4).
            """
            logical_date = context.get("logical_date") or context["dag_run"].run_after
            db = Database.from_env()
            ledger = PostgresLedger(db)
            store = MinioObjectStore.from_env()
            publisher = KafkaEventPublisher.from_env()

            run_id = flow.run_id_of(logical_date)
            # 소스별 건수가 그대로 요약 이벤트의 `emitted` 가 된다. 장부를 구간으로
            # 다시 세지 않는 이유는 실행이 겹치면 앞 실행 몫까지 세기 때문이다.
            counts = flow.publish_pending(
                ledger=ledger,
                publisher=publisher,
                bucket=store.bucket,
                domain=domain,
                run_id=run_id,
                now=pendulum.now("UTC"),
            )
            statuses = flow.source_statuses(
                keys,
                flow.outcomes_from_xcom(context["ti"].xcom_pull(task_ids=COLLECT_TASK_ID)),
                domain_of,
            )
            summary_publisher = KafkaEventPublisher.from_env_optional(topic_env=SUMMARY_TOPIC_ENV)
            if summary_publisher is None:
                logger.info("%s가 비어 있어 실행 요약 발급을 건너뛴다", SUMMARY_TOPIC_ENV)
                summaries = 0
            else:
                summaries = flow.publish_summaries(
                    publisher=summary_publisher,
                    run_id=run_id,
                    logical_date=logical_date,
                    statuses=statuses,
                    counts=counts,
                )
            return {
                "articles": sum(stats.count for stats in counts.values()),
                "summaries": summaries,
                "summary_enabled": summary_publisher is not None,
                "failed_sources": [s.source for s in statuses if s.status == "failed"],
            }

        # 자산은 **발급과 떼어 놓는다** (S15P21A102-247 코드리뷰).
        #
        # 소비 측이 읽는 것은 `collected_article` 행이고 그 행은 `collect_one` 이 적는다.
        # 그런데 자산을 `publish` 에 걸면 Kafka 브로커가 죽었을 때 그 태스크가 실패하고,
        # 실패한 태스크는 자산을 내지 않는다 — 읽을 행이 다 있는데 `spark_ingest` 만 안
        # 깨어난다. 읽기는 Kafka 와 무관해졌는데 깨우기만 브로커에 묶여 있는 꼴이다.
        #
        # `ALL_DONE` 이라 앞이 실패해도 돈다. 그래도 되는 이유는 이 신호의 뜻이 "수집이
        # 전부 성공했다" 가 아니라 "이번 회차가 끝났고 장부에 적을 것은 적혔다" 라서다.
        # 한 소스가 죽어도 다른 소스가 받아 둔 기사는 처리되어야 한다.
        #
        # ⚠️ **`publish` 가 사라지면 이 태스크도 자리를 옮긴다.** Kafka 발행을 걷어낼 때
        # (3단계) 여기가 `collect_one` 바로 뒤가 된다.
        @task(task_id=SIGNAL_TASK_ID, trigger_rule=TriggerRule.ALL_DONE, outlets=[COLLECTED])
        def signal_collected() -> None:
            """이번 회차가 끝났다고 알린다. 하는 일은 자산을 내는 것뿐이다."""
            logger.info("수집 회차 종료 — %s 자산을 낸다", COLLECTED.name)

        keys = list(source_keys)
        (
            ensure_schema()
            >> collect_one.expand(source_key=keys)
            >> publish(keys)
            >> signal_collected()
        )

    return collect_dag()
