"""개발 트렌드 예제 DAG — 규약 견본. 팀원 설계서 v0.1 의 collect_documents 모양.

소스 목록 → 소스별 동적 매핑 수집 → 집계. 한 소스의 실패가 다른 소스를 막지 않도록
집계는 trigger_rule=ALL_DONE 이다(none_failed_min_one_success 는 부분 실패에 막힌다).
DAG 파일엔 실행 순서만 두고, 함수는 trendin.dev.example 에 있다.
"""

from datetime import timedelta

import pendulum
from airflow.sdk import TriggerRule, dag, task

from trendin.dev import example


@dag(
    dag_id="dev_example",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["dev", "example"],
    doc_md=__doc__,
)
def dev_example():
    @task
    def load_active_sources() -> list[str]:
        return example.load_active_sources()

    @task(pool="crawler_pool")
    def collect_source(source: str) -> int:
        """소스 하나 수집. 매핑 인스턴스는 서로 독립적으로 실패한다."""
        return example.collect_source(source)

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def save_collection_metrics(counts: list[int]) -> int:
        """끝난 것만 모아 합친다. XCom 엔 건수 하나만."""
        return example.save_collection_metrics(counts)

    save_collection_metrics(collect_source.expand(source=load_active_sources()))


dev_example()
