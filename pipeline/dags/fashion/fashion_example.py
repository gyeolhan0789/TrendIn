"""패션 예제 DAG — 규약 견본.

제출 → reschedule 센서로 완료 대기 → 수거. 실제 부품 DAG 는 이 모양을 베껴 쓴다.
DAG 파일엔 실행 순서만 두고, 함수는 trendin.fashion.example 에 있다.
"""

from datetime import timedelta

import pendulum
from airflow.sdk import PokeReturnValue, dag, task

from trendin.fashion import example


@dag(
    dag_id="fashion_example",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 9, 1, tz="Asia/Seoul"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=1)},
    tags=["fashion", "example"],
    doc_md=__doc__,
)
def fashion_example():
    @task(pool="crawler_pool")
    def submit() -> str:
        """더미 배치 잡을 제출한다. XCom 엔 job_id 하나만."""
        return example.submit_job()

    @task.sensor(poke_interval=30, timeout=600, mode="reschedule")
    def wait(job_id: str) -> PokeReturnValue:
        """잡이 끝날 때까지 기다린다. 대기 중엔 슬롯을 반납한다(reschedule). 실제론 10~15분 간격."""
        return PokeReturnValue(is_done=example.job_is_done(job_id), xcom_value=job_id)

    @task
    def collect(job_id: str) -> int:
        """앱 DB 에 붙어 결과를 수거한다. 반환값은 건수 하나."""
        return example.collect(job_id)

    collect(wait(submit()))


fashion_example()
