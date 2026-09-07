"""dev 도메인 주기 수집 — 골격 (S15P21A102-167, 소스는 S15P21A102-165 가 채운다).

`fashion_collect` 와 **같은 모양을 쓴다** — 실행 흐름은 도메인을 모른다. 165 가 할 일은
`trendin/dev/collect/` 에 소스 정의와 어댑터를 두고, 아래 `source_keys` 와 `collect` 를
채우는 것뿐이다.

지금은 `source_keys` 가 비어 있어 수집 태스크가 한 번도 실행되지 않는다(빈 매핑은 건너뛴다).
발급 태스크는 도메인으로 잘라 읽으므로 fashion 행을 건드리지 않고, dev 행이 아직 없으니 낼
것도 없다.
"""

# DAG 파서는 파일 안에 `airflow` 와 `dag` 가 든 파일만 읽는다(안전 모드).
# 이 파일은 설정만 들어 airflow 를 직접 import 하지 않으므로 그 표시를 여기 남긴다.
from trendin.common.collect.dag_factory import build_collect_dag

dev_collect = build_collect_dag(
    dag_id="dev_collect",
    domain="dev",
    schedule="*/30 * * * *",  # hn 30분 (설계 문서 #9 잠정값)
    source_keys=(),
    domain_of=lambda key: "dev",
    collect=None,
    doc_md=__doc__,
)
