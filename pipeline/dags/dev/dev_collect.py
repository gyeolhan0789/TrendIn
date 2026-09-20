"""Hacker News 주기 수집 (S15P21A102-165).

`fashion_collect` 와 **같은 모양을 쓴다** — 실행 흐름은 도메인을 모른다. 매 실행이 최근
6시간에 올라온 story 를 Algolia 에 묻고, 앞 실행과 겹친 글은 장부가 거른다. 6시간보다 오래
멈췄다면 그 구간은 주기 실행이 메우지 않는다 — `trendin.dev.collect.backfill` 로 받는다.

모양은 `trendin.common.collect.dag_factory` 에 있고 여기는 설정만 든다(README 규약 1).
"""

# DAG 파서는 파일 안에 `airflow` 와 `dag` 가 든 파일만 읽는다(안전 모드).
# 이 파일은 설정만 들어 airflow 를 직접 import 하지 않으므로 그 표시를 여기 남긴다.
from trendin.common.collect.dag_factory import build_collect_dag
from trendin.dev.collect import runner, sources

dev_collect = build_collect_dag(
    dag_id="dev_collect",
    domain="dev",
    schedule="*/30 * * * *",  # hn 30분 (설계 문서 #9 잠정값)
    source_keys=runner.SOURCE_KEYS,
    source_countries={key: source.country for key, source in sources.BY_KEY.items()},
    collect=runner.collect,
    doc_md=__doc__,
)
