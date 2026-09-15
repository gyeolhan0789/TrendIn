"""ingest — 수집 장부의 뷰를 읽어 정제하고 `curated`·`contents` 에 쓴다 ([02]·[03]).

모양은 `trendin.spark.dag_factory` 에 있고 여기는 설정만 든다 (README 규약 1).

**도메인별로 나누지 않는다.** 장부 뷰가 하나이고 도메인은 행 안에 있다.

⚠️ **이 파일에 `airflow` 라는 낱말이 있어야 한다.** Airflow 의 안전 모드 탐색(`DagBag`)이
파일 내용에 `dag` 과 `airflow` 가 **둘 다** 있을 때만 파싱한다. 없으면 import 오류도 없이
조용히 목록에서 빠진다 — 2026-09-10 에 실제로 그렇게 셋 다 사라졌다.

**수집이 끝나면 깨어난다** (S15P21A102-247). 전에는 `collect` 가 정각, 이쪽이 30분이라
둘이 시계 차이로만 묶여 있었다. 수집이 늦으면 빈손으로 돌고 다음 회차가 메우는 식이었는데,
그게 티가 안 났던 이유는 Kafka 가 못 받은 몫을 들고 있었기 때문이다. 브로커를 걷으면서
`dag_factory` 가 "단계 사이의 의존을 크론 간격이 아니라 자산으로 건다" 고 적어 둔 원칙을
여기에도 적용한다 — `ingest → extract` 가 이미 그렇게 이어져 있다.

**오래 멈추면 백필이 필요하다.** 장부는 지우지 않으므로 행은 그대로 있지만, 읽는 창이
`ingest.ledger.lookback_hours`(기본 168시간)다. 그보다 오래 안 돌면 그 사이 기사는
`--source objects` 로 넣는다.

**새 기사가 없으면 skipped 로 끝난다** (S15P21A102-247). 수집이 하루 일흔 번 넘게 깨우는데
그 대부분은 새 기사가 없다. 그때마다 `curated` 자산을 내면 `spark_extract` 가 30일 코퍼스를
헛돈다 — 결과는 같고 시간만 쓴다. 그래서 Job 이 쓴 것이 없으면 종료 코드 99 로 끝내고
(`trendin.spark.common.exit_codes.NOTHING_NEW`) Airflow 가 그것을 skipped 로 읽는다.
skipped 는 자산을 갱신하지 않는다.

⚠️ **실패가 아니다.** UI 에서 흰색(skipped)으로 보이는 회차는 정상이다. 빨간색이면 진짜
문제고, 그 구분이 생긴 것이 이 장치의 목적이다.
"""

from __future__ import annotations

from datetime import timedelta

from trendin.common.collect.dag_factory import COLLECTED
from trendin.spark.dag_factory import CURATED, build_spark_dag

spark_ingest = build_spark_dag(
    dag_id="spark_ingest",
    schedule=[COLLECTED],
    job="ingest",
    # 창 안의 행을 한 번에 읽어 배치 하나로 돈다. 그래도 상한을 둔다 — 안 두면 죽은 실행이
    # `max_active_runs=1` 을 붙잡아 다음 회차가 영영 안 돈다.
    execution_timeout=timedelta(hours=2),
    outlets=[CURATED],
    doc_md=__doc__,
)
