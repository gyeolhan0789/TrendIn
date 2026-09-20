"""패션 매거진 7곳 주기 수집 (S15P21A102-167).

순서는 스키마 확인 → 소스별 수집 → 회차 종료 신호다. 소스별 태스크는 서로 독립이라
하나가 죽어도 나머지는 돈다. 신호는 `ALL_DONE` 이라 일부가 죽어도 나가고, 살아남은
소스가 받아 둔 기사는 그 신호로 깨어난 `spark_ingest` 가 처리한다.

모양은 `trendin.common.collect.dag_factory` 에 있고 여기는 설정만 든다(README 규약 1).
"""

# DAG 파서는 파일 안에 `airflow` 와 `dag` 가 든 파일만 읽는다(안전 모드).
# 이 파일은 설정만 들어 airflow 를 직접 import 하지 않으므로 그 표시를 여기 남긴다.
from trendin.common.collect.dag_factory import build_collect_dag
from trendin.fashion.collect import runner, sources

fashion_collect = build_collect_dag(
    dag_id="fashion_collect",
    domain="fashion",
    schedule="0 * * * *",  # 매시 정각 KST (설계 문서 #9 잠정값)
    source_keys=runner.SOURCE_KEYS,
    source_countries={key: source.country for key, source in sources.BY_KEY.items()},
    collect=runner.collect,
    doc_md=__doc__,
)
