"""dags/ 아래 모든 DAG 파일이 import 오류 없이 읽히는지."""

import json
from pathlib import Path

from airflow.dag_processing.dagbag import DagBag

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"
POOLS_JSON = Path(__file__).resolve().parents[1] / "pools.json"
EXPECTED_DAG_IDS = {"fashion_example", "dev_example", "fashion_collect", "dev_collect"}


def load_bag() -> DagBag:
    # known_pools 를 주면 pools.json 에 없는 pool 을 쓰는 태스크가 경고로 드러난다.
    known_pools = {"default_pool", *json.loads(POOLS_JSON.read_text())}
    return DagBag(dag_folder=str(DAGS_DIR), known_pools=known_pools)


def test_dags_import_without_errors():
    bag = load_bag()
    assert bag.import_errors == {}
    assert EXPECTED_DAG_IDS <= set(bag.dag_ids)


def test_dag_ids_carry_domain_prefix():
    for dag_id in load_bag().dag_ids:
        assert dag_id.startswith(("fashion_", "dev_")), dag_id


def test_tasks_use_only_known_pools():
    known_pools = {"default_pool", *json.loads(POOLS_JSON.read_text())}
    for dag in load_bag().dags.values():
        for task in dag.tasks:
            assert task.pool in known_pools, f"{dag.dag_id}.{task.task_id} pool={task.pool!r}"
