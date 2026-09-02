"""pytest 공통 설정. Airflow 를 import 하기 전에 홈 디렉터리와 설정을 격리한다."""

import os
import tempfile

_AIRFLOW_HOME = tempfile.mkdtemp(prefix="airflow-test-")
os.environ.setdefault("AIRFLOW_HOME", _AIRFLOW_HOME)
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__DEFAULT_TIMEZONE", "Asia/Seoul")
