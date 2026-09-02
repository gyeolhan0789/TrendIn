"""fashion_example DAG 의 태스크 함수.

Airflow 에 의존하지 않는 함수(submit_job · job_is_done)는 그대로 단위 테스트한다.
Airflow Connection 을 쓰는 함수(collect)는 컨테이너 안 DAG 실행으로 검증한다.
"""

import time

JOB_PREFIX = "demo-"
JOB_DURATION_SECONDS = 60


def submit_job(now: float | None = None) -> str:
    """더미 배치 잡을 제출한다.

    job_id 에 제출 시각을 넣어, 상태를 어디에도 저장하지 않고 완료 여부를 판정할 수 있게 한다.
    실제 부품은 제공자가 준 배치 ID 를 그대로 돌려준다. XCom 엔 이 문자열 하나만 실린다.
    """
    submitted = int(now if now is not None else time.time())
    return f"{JOB_PREFIX}{submitted}"


def submitted_at(job_id: str) -> int:
    if not job_id.startswith(JOB_PREFIX):
        raise ValueError(f"알 수 없는 job_id: {job_id!r}")
    return int(job_id[len(JOB_PREFIX) :])


def job_is_done(job_id: str, now: float | None = None) -> bool:
    """제출 후 JOB_DURATION_SECONDS 가 지났으면 완료. 센서가 poke 마다 부른다."""
    current = now if now is not None else time.time()
    return current - submitted_at(job_id) >= JOB_DURATION_SECONDS


def collect(job_id: str) -> int:
    """앱 DB 접속 규약 확인: Connection `app_db`(환경변수 AIRFLOW_CONN_APP_DB) 로 SELECT 1.

    실제 부품은 여기서 배치 결과를 받아 테이블에 쓴다. 반환값은 건수 하나.
    """
    from airflow.providers.postgres.hooks.postgres import PostgresHook  # 태스크 안에서만 import

    submitted_at(job_id)  # job_id 형식 검증
    row = PostgresHook(postgres_conn_id="app_db").get_first("SELECT 1")
    return int(row[0])
