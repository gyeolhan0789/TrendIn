"""extract — `curated` 를 읽어 키워드 후보를 뽑고 승격까지 간다 ([04]·[05]).

**`ingest` 가 성공했을 때만 돈다.** 크론 간격이 아니라 자산(`CURATED`)으로 잇는다 — `ingest`
가 몇 분 걸리는지 모르는 채로 시각을 박으면 느린 회차에서 빈손으로 돈다.

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**도메인별 태스크로 나눈다.** 세 Job 중 도메인을 아는 것은 이것뿐이고([04 §8] 도메인별 옵션),
한 도메인의 코퍼스가 깨져도 다른 도메인은 도는 편이 낫다.

## ⚠️ 도메인은 하나씩 돈다

GLiNER 를 올리는 Job 은 이것뿐이고, 워커 하나가 RSS 2.3GB 다(2026-09-17 실측). 데이터
EC2(4 CPU · 15GB)는 워커 셋에서 죽는다. 그래서 자원 상한이 세 겹이다.

| 축 | 값 | 어디에 |
| --- | --- | --- |
| 태스크당 워커 수 | `local[2]` | 이 파일의 `env` |
| 한 배치의 피크 | `words 768 · size 8` | `spark/conf/dev.yaml` |
| **동시에 도는 태스크 수** | **1** | 이 파일의 `one_at_a_time` |

셋째 줄이 없던 2026-09-20 11:19 에 `dev` 와 `fashion` 이 같이 떠서 호스트가 굳었다 — OOM
킬이 아니라 커널 동결이라 SSH 도 안 되고 콘솔 재부팅이 필요했다. 태스크 둘 × `local[2]`
는 워커 넷이고, 그날 서버에 있던 파일은 `env` 도 없어 여덟이었다.

**재시도는 없다.** 죽는 원인이 자원이라 5분 뒤에 다시 돌려도 같은 자리에서 죽고, 그 사이
사람이 손을 못 댄다. 재부팅 직후에는 스케줄러가 죽었던 태스크를 **1분 안에** 재시도하는데,
그때 `pause` 는 이미 뜬 태스크를 멈추지 못한다. 고치고 나서 사람이 다시 돌리는 쪽이 맞다.

🚫 **승격은 백엔드에 막혀 있다.** `keywords (domain, normalized_name)` UNIQUE 가 없으면
([08 §5] 티어 1) 승격만 건너뛰고 나머지는 돈다. 그 상태에서는 `aggregate` 가 0행을 낸다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.spark.dag_factory import CURATED, KEYWORDS, build_spark_dag

spark_extract = build_spark_dag(
    dag_id="spark_extract",
    schedule=[CURATED],
    job="extract",
    task_args={
        "fashion": ("--domain", "fashion"),
        "dev": ("--domain", "dev"),
    },
    # 기본값 `local[*]` 은 4 CPU 서버에서 워커 넷을 띄운다. 손 실행에만 붙던 조건을 DAG 에도
    # 준다 — 그 전에는 자동 실행이 문서가 적을 때만 우연히 살아 있었다.
    env={"SPARK_MASTER": "local[2]"},
    one_at_a_time=True,
    retries=0,
    # 2시간이면 레지스트리가 쓰기 전에 잘린다. 2026-09-23 밤부터 매 실행이 오타 변형 탐색
    # (`registry/merge.variant_pairs`, 운영 후보 21만에서 로컬 측정 42분) 도중 죽어 키워드 승격이
    # 멈췄고 24H 가 비었다 (S15P21A102-395). 탐색을 줄이면 다시 본다.
    execution_timeout=timedelta(hours=3),
    outlets=[KEYWORDS],
    doc_md=__doc__,
)
