"""Job 프로세스의 종료 코드. **Airflow 와 Spark 가 같이 읽는 값이라 여기 하나만 둔다.**

`dag_factory.py` 는 Airflow 컨테이너에서 DagBag 이 파싱하고 `cli.py` 는 `spark-submit` 안에서
돈다. 두 곳이 숫자를 각자 적으면 한쪽만 고쳐졌을 때 **아무 오류 없이** 어긋난다 — Job 은
"새로 쓴 것이 없다" 고 99 를 내는데 Airflow 는 그것을 실패로 읽어 재시도를 돌리는 식이다.

이 모듈은 **아무것도 import 하지 않는다.** 그래야 pyspark 가 없는 Airflow 기본 이미지에서도
DAG 파싱이 이 값을 읽을 수 있다 (`session.py` 가 pyspark 를 `TYPE_CHECKING` 아래 둔 것과
같은 이유).
"""

from __future__ import annotations

OK = 0
CONFIG = 2

# 정상 종료인데 **새로 쓴 것이 없다.** `BashOperator.skip_on_exit_code` 의 기본값이 99 라
# 이 코드로 끝나면 태스크가 실패가 아니라 skipped 가 되고, skipped 는 자산을 갱신하지 않는다.
# 그래서 뒤 단계(`spark_extract`)가 빈손으로 깨어나지 않는다 (S15P21A102-247).
#
# 실패로 내면 안 된다 — 새 기사가 없는 회차는 정상이고, 재시도해도 결과가 같다.
NOTHING_NEW = 99
