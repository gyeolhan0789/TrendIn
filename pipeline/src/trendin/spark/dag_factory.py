"""Spark Job 하나를 도는 DAG 을 만든다 — `ingest` · `extract` · `aggregate` 가 공유한다.

모양이 셋 다 같다: **`spark/scripts/submit.sh <job>` 을 부르고 종료 코드를 본다.** 그래서
DAG 파일에는 설정만 남고 흐름은 여기 있다 (`collect/dag_factory.py` 와 같은 규약,
`pipeline/README.md` 규약 1).

## 왜 `BashOperator` 인가

`SparkSubmitOperator` 를 쓰지 않는다. 이유가 둘이다.

**프로바이더가 없다.** `apache-airflow-providers-apache-spark` 가 이미지에 없다. 넣는 것은
별건이다.

**설정이 두 곳으로 갈린다.** `submit.sh` 가 이미 jar 목록 · log4j · 드라이버 파이썬을
감싼다. 그걸 Airflow Connection 으로 옮기면 같은 값이 두 군데 살고, 한쪽만 고쳐졌을 때 조용히
갈린다 — `spark/versions.sh` 를 "버전의 단일 출처" 로 둔 것과 같은 이유다.

대가는 Airflow UI 에서 Spark 애플리케이션으로 가는 링크가 없다는 것이다. 종료 코드와 로그만
본다. 지금 규모에서 받아들일 만하다.

## ⚠️ Spark 오버레이로 띄워야 돈다

`spark/scripts` 는 **기본 compose 에 마운트되지 않는다.** `spark/compose.spark.yaml` 이
`./spark:/opt/airflow/spark` 를 얹고 이미지도 pyspark·jar 가 든 것으로 바꾼다.

```sh
docker compose -f compose.yaml -f spark/compose.spark.yaml up -d
```

기본 compose 로만 띄우면 이 DAG 들은 `submit.sh: No such file` 로 죽는다. 조용히 건너뛰지
않고 죽는 쪽이 맞다 — 반쯤 도는 파이프라인이 가장 나쁘다.

## ⚠️ DAG 파일에 `airflow` 라는 낱말이 있어야 한다

Airflow 의 안전 모드 탐색이 파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 그 파일을
파싱한다. 이 팩토리를 쓰는 DAG 파일은 `from trendin.spark.dag_factory import ...` 만 하므로
`airflow` 가 안 나올 수 있고, 그러면 **import 오류도 없이 조용히 목록에서 빠진다.**
2026-09-10 에 실제로 셋 다 그렇게 사라졌다 — 오류가 아니라 부재라 알아채기 어렵다.

## 도메인을 DAG 으로 나누지 않는다

`collect` 는 도메인별 DAG 인데(소스가 도메인별이라) 여기는 아니다. **Job 들이 도메인을 그렇게
보지 않기 때문이다.**

| Job | 도메인 |
| --- | --- |
| `ingest` | 토픽 하나(`raw-file-ready`)를 소비한다. 도메인은 이벤트 안에 있다 ([02 §1]) |
| `extract` | **유일하게 도메인을 안다** (`--domain`). 그래서 이쪽만 도메인별 태스크로 나눈다 |
| `aggregate` | `--domain` 인자가 아예 없다. 원자료 전체를 한 번에 본다 ([07 §5]) |
"""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import Asset, dag

# 숫자 하나를 위해 import 하는 것이 아니라, Job 쪽과 **같은 값**을 읽으려고 한다. 이 모듈은
# 아무것도 import 하지 않으므로 pyspark 없는 Airflow 이미지에서도 DagBag 이 읽는다.
from trendin.spark.common.exit_codes import NOTHING_NEW

# 수집·집계가 모두 KST 기준이다 (불변식 10, [07 §2]).
KST = "Asia/Seoul"

# 단계 사이의 의존을 **크론 간격이 아니라 자산으로** 건다. `ingest` 가 몇 분 걸리는지 모르는
# 채로 `extract` 를 15분 뒤에 걸면, 느린 회차에서 둘이 겹치거나 빈손으로 돈다.
#
# `aggregate` 만 자산이 아니라 시각에 걸린다 — 기준일 D 가 KST 자정으로 끊기고([07 §4])
# 백엔드가 자기 시계로 같은 구간을 계산해 등호로 조회하기 때문이다. 자정 직후에 돌지 않으면
# 그날 목록이 **빈다**.
CURATED = Asset("trendin://curated")
KEYWORDS = Asset("trendin://keywords")
METRICS = Asset("trendin://metrics")

# 컨테이너 안에서 `spark/compose.spark.yaml` 이 저장소의 `spark/` 를 여기에 붙인다.
SPARK_HOME_IN_CONTAINER = "/opt/airflow/spark"
SUBMIT = f"{SPARK_HOME_IN_CONTAINER}/scripts/submit.sh"

# 프로파일은 환경변수로 온다 (`SPARK_JOB_PROFILE`, [09 §3]). DAG 이 프로파일을 박지 않는
# 이유는 같은 DAG 이 로컬·dev·운영에서 그대로 돌아야 하기 때문이다.
_COMMAND = 'set -euo pipefail; "$SUBMIT" {job} {args}'


class SubmitOperator(BashOperator):
    """`submit.sh` 를 부르는 BashOperator. 템플릿 파일 탐색을 끄고 종료 코드를 읽는다.

    ## 새로 쓴 것이 없으면 skipped 다

    Job 이 `NOTHING_NEW`(99) 로 끝나면 실패가 아니라 **skipped** 다. `skip_on_exit_code` 의
    기본값이 마침 99 지만 여기 적어 둔다 — 값이 어디서 오는지 보이지 않으면 Job 쪽 상수를
    고칠 때 이 자리가 같이 눈에 들어오지 않는다.

    **skipped 는 자산을 갱신하지 않는다.** 그것이 목적이다. `spark_ingest` 가 수집 회차마다
    깨어나는데 새 기사는 대개 없고, 그때마다 `curated` 자산을 내면 `spark_extract` 가 30일
    코퍼스를 헛돈다 (S15P21A102-247).

    `BashOperator` 의 `template_ext` 는 `(".sh", ".bash")` 다. 템플릿 필드(`bash_command` ·
    `env` · `cwd`)의 값이 그 확장자로 끝나면 Jinja 가 그것을 **읽어올 파일 경로**로 보고
    DAG 폴더에서 찾는다. 아래 `env` 의 `SUBMIT` 이 `submit.sh` 로 끝나서, 배포 직후 첫
    실행이 `TemplateNotFound: not found in search path: '/opt/airflow/dags/pipeline'` 으로
    죽었다 — `spark-submit` 에 닿지도 못했다.

    확장자 목록을 비워 그 탐색을 끈다. 이 연산자가 파일을 읽을 일은 없고, 이렇게 두면
    나중에 인자가 `.sh` 로 끝나는 경우까지 함께 막힌다.
    """

    template_ext = ()

    def __init__(self, **kwargs):
        kwargs.setdefault("skip_on_exit_code", NOTHING_NEW)
        super().__init__(**kwargs)


def submit_command(job: str, *args: str) -> str:
    """`submit.sh <job> <args...>` 한 줄. 인자에 공백이 있으면 부른 쪽이 따옴표를 넣는다."""
    return _COMMAND.format(job=job, args=" ".join(args))


def build_spark_dag(
    *,
    dag_id: str,
    schedule,
    job: str,
    doc_md: str,
    task_args: dict[str, Sequence[str]] | None = None,
    outlets: Sequence[Asset] = (),
    retries: int = 2,
    execution_timeout: timedelta | None = None,
    start_date=None,
    env: dict[str, str] | None = None,
):
    """Spark Job 하나짜리 DAG.

    `task_args` 가 `None` 이면 태스크 하나(`run`)가 인자 없이 Job 을 부른다. 사전을 주면
    **태스크 이름 → 인자** 로 여러 태스크를 만든다 — `extract` 가 도메인별로 그렇게 쓴다.
    태스크들은 서로 독립이라 한쪽이 죽어도 다른 쪽은 돈다.

    `schedule` 은 크론 문자열이거나 자산 목록이다. `outlets` 를 주면 태스크가 성공할 때 그
    자산이 갱신되고, 그것을 `schedule` 로 받는 DAG 이 이어서 돈다.

    `env` 는 그 Job 에만 주는 환경변수다. 컨테이너 환경을 그대로 물려받고(`append_env`)
    여기 준 것만 덮는다 — Job 마다 자원 요구가 달라 한 곳에 박을 수 없다
    (`spark_extract` 의 `SPARK_MASTER` 가 그 자리다).

    `max_active_runs=1` 은 선택이 아니다. 처리 이력과 DLQ 가 스테이징 테이블을 공유하므로
    ([08 §3]) 두 실행이 겹치면 한쪽 행이 다른 쪽 트랜잭션에 딸려 들어간다.

    태스크가 **성공했을 때만** `outlets` 의 자산이 갱신된다. 죽어도, 새로 쓴 것이 없어
    skipped 로 끝나도 안 갱신된다 (`SubmitOperator`).
    """

    @dag(
        dag_id=dag_id,
        schedule=schedule,
        start_date=start_date or pendulum.datetime(2026, 9, 1, tz=KST),
        # 켜면 밀린 회차가 한꺼번에 돈다. `ingest` 는 장부를 거슬러 읽는 창이, `aggregate` 는
        # 소급 재계산 구간이 이미 "밀린 것" 을 따라잡으므로 회차를 쌓을 이유가 없다.
        catchup=False,
        max_active_runs=1,
        default_args={
            "retries": retries,
            "retry_delay": timedelta(minutes=5),
            "execution_timeout": execution_timeout,
        },
        tags=["spark", job],
        doc_md=doc_md,
    )
    def spark_dag():
        for task_id, args in (task_args or {"run": ()}).items():
            SubmitOperator(
                task_id=task_id,
                bash_command=submit_command(job, *args),
                cwd=SPARK_HOME_IN_CONTAINER + "/..",
                env={"SUBMIT": SUBMIT, **(env or {})},
                append_env=True,
                # 태스크가 **성공했을 때만** 자산이 갱신된다. 죽으면 다음 단계가 안 돈다 —
                # 크론이었다면 빈손으로 돌았을 자리다.
                outlets=list(outlets),
            )

    return spark_dag()
