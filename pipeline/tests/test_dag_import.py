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


def test_spark_태스크는_새_것_없음을_skip_으로_읽는다():
    """Job 이 `NOTHING_NEW` 로 끝나면 실패가 아니라 skipped 다 (S15P21A102-247).

    **skipped 는 자산을 갱신하지 않는다.** 그래서 새 기사가 없는 회차가 `spark_extract` 를
    깨우지 않는다. 숫자를 `exit_codes` 에서 읽어 비교하는 것이 요점이다 — 한쪽만 바뀌면
    Job 은 "쓴 것 없음" 을 내는데 Airflow 는 그것을 실패로 읽어 재시도를 돌린다.
    """
    from trendin.spark.common.exit_codes import NOTHING_NEW

    bag = load_bag()
    for dag_id in ("spark_ingest", "spark_extract", "spark_aggregate"):
        for task in bag.dags[dag_id].tasks:
            # `BashOperator` 가 값을 목록으로 정규화한다 (`99` → `[99]`). 어느 쪽으로 와도
            # 같게 보도록 펴서 비교한다 — 정규화 방식은 Airflow 사정이라 바뀔 수 있다.
            codes = task.skip_on_exit_code
            codes = [codes] if isinstance(codes, int) else sorted(codes or ())
            assert codes == [NOTHING_NEW], f"{dag_id}.{task.task_id} → {codes!r}"


def test_수집_DAG_이_ingest_를_깨울_자산을_낸다():
    """크론 간격이 아니라 자산으로 잇는다 (S15P21A102-247). 수집이 늦으면 `ingest` 가
    빈손으로 돌던 자리였고, Kafka 가 못 받은 몫을 들고 있어서 티가 안 났다.

    자산은 **마지막 태스크**에 달려야 한다. 앞에 달면 장부에 이번 회차가 다 적히기 전에
    소비 측이 깨어난다.
    """
    from trendin.common.collect.dag_factory import COLLECTED

    bag = load_bag()
    for dag_id in ("fashion_collect", "dev_collect"):
        dag = bag.dags[dag_id]
        emitters = [t.task_id for t in dag.tasks if any(a.uri == COLLECTED.uri for a in t.outlets)]
        assert emitters, f"{dag_id} 가 {COLLECTED.uri} 를 내지 않는다"
        for task_id in emitters:
            downstream = dag.get_task(task_id).downstream_list
            assert not downstream, f"{dag_id}.{task_id} 뒤에 태스크가 있다"


def test_자산을_내는_태스크는_Kafka_발행과_떨어져_있다():
    """**Kafka 가 죽어도 `ingest` 는 깨어나야 한다** (S15P21A102-247 코드리뷰).

    소비 측이 읽는 것은 `collected_article` 행이고 그 행은 수집 태스크가 적는다. 자산을
    발행 태스크에 걸면 브로커가 죽었을 때 그 태스크가 실패하고, 실패한 태스크는 자산을
    내지 않는다 — 읽을 행이 다 있는데 뒤 단계만 안 깨어난다.

    두 가지를 본다. 자산을 내는 태스크가 발행 태스크가 **아닐 것**, 그리고 앞이 실패해도
    돌도록 `ALL_DONE` 일 것.
    """
    from airflow.sdk import TriggerRule

    from trendin.common.collect.dag_factory import COLLECTED, SIGNAL_TASK_ID

    bag = load_bag()
    for dag_id in ("fashion_collect", "dev_collect"):
        dag = bag.dags[dag_id]
        emitters = [t for t in dag.tasks if any(a.uri == COLLECTED.uri for a in t.outlets)]
        assert [t.task_id for t in emitters] == [SIGNAL_TASK_ID]
        for task in emitters:
            assert task.trigger_rule == TriggerRule.ALL_DONE, task.task_id
        # 발행 태스크는 자산을 내지 않는다. 이름으로 찾는 이유는 그 태스크가 3단계에서
        # 사라질 예정이라, 없어졌을 때 이 시험이 조용히 통과하면 안 되기 때문이다.
        publish = dag.get_task("publish")
        assert not publish.outlets, f"{dag_id}.publish 가 자산을 낸다"
