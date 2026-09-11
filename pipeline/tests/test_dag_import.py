"""dags/ 아래 모든 DAG 파일이 import 오류 없이 읽히는지."""

import json
from pathlib import Path

from airflow.dag_processing.dagbag import DagBag

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"
POOLS_JSON = Path(__file__).resolve().parents[1] / "pools.json"
EXPECTED_DAG_IDS = {
    "fashion_example",
    "dev_example",
    "fashion_collect",
    "dev_collect",
    # Spark 세 단계 (2026-09-10). **목록에 있는 것이 시험의 요점이다** — Airflow 의 안전 모드
    # 탐색은 파일에 `dag` 과 `airflow` 가 둘 다 없으면 import 오류도 없이 건너뛴다. 그때
    # `import_errors` 는 비어 있고 DAG 만 사라지므로, 이름을 적어 두지 않으면 아무도 모른다.
    "spark_ingest",
    "spark_extract",
    "spark_aggregate",
}


def load_bag() -> DagBag:
    # known_pools 를 주면 pools.json 에 없는 pool 을 쓰는 태스크가 경고로 드러난다.
    known_pools = {"default_pool", *json.loads(POOLS_JSON.read_text())}
    return DagBag(dag_folder=str(DAGS_DIR), known_pools=known_pools)


def test_dags_import_without_errors():
    bag = load_bag()
    assert bag.import_errors == {}
    assert EXPECTED_DAG_IDS <= set(bag.dag_ids)


def test_dag_ids_carry_scope_prefix():
    """DAG 이름은 **무엇에 매인 것인지**로 시작한다.

    도메인에 매인 것은 `fashion_`·`dev_` 다 — 소스가 도메인별이라 수집이 그렇다.
    `spark_` 는 도메인에 매이지 않은 것이다. Spark Job 셋 중 도메인을 아는 것은 `extract`
    뿐이고(`ingest` 는 토픽 하나를 소비, `aggregate` 는 `--domain` 인자가 없다) 그 하나도
    DAG 이 아니라 **태스크**로 나뉜다. 그래서 접두를 도메인으로 붙일 수 없다.
    """
    for dag_id in load_bag().dag_ids:
        assert dag_id.startswith(("fashion_", "dev_", "spark_")), dag_id


def test_tasks_use_only_known_pools():
    known_pools = {"default_pool", *json.loads(POOLS_JSON.read_text())}
    for dag in load_bag().dags.values():
        for task in dag.tasks:
            assert task.pool in known_pools, f"{dag.dag_id}.{task.task_id} pool={task.pool!r}"
