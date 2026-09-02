# TrendIn 파이프라인 이미지. 정식 이미지 위에 우리 패키지(src/trendin)를 editable 로 얹는다.
# 컴포즈가 ./src 를 같은 경로에 바인드 마운트하므로 로컬 수정이 재빌드 없이 반영된다.
ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.12
FROM apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}
ARG AIRFLOW_VERSION
ARG PYTHON_VERSION

USER airflow
WORKDIR /opt/airflow
COPY --chown=airflow:0 pyproject.toml README.md ./
COPY --chown=airflow:0 src ./src

# Airflow 핀을 반복해 두면 constraints 와 어긋날 때 조용히 바뀌지 않고 설치가 실패한다 (docker-stack 문서).
RUN pip install --no-cache-dir \
      "apache-airflow==${AIRFLOW_VERSION}" \
      -e /opt/airflow \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"
