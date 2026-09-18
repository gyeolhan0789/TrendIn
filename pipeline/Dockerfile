# TrendIn 파이프라인 이미지. 정식 이미지 위에 우리 패키지(src/trendin)를 editable 로 얹는다.
# 컴포즈가 ./src 를 같은 경로에 바인드 마운트하므로 로컬 수정이 재빌드 없이 반영된다.
#
# --- 이 파일이 만드는 층은 언제나 이미지의 맨 위다 (2026-09-18) ---------------
# src 는 일주일에 열 번 넘게 바뀌고, 바뀌면 그 위에 쌓인 층은 전부 캐시를 잃는다. 그래서
# 무거운 것을 이 위에 얹으면 소스 한 줄마다 그것을 통째로 다시 만들게 된다. 무거운 것은
# BASE_IMAGE 로 받아 아래에 깐다 (spark/Dockerfile 이 그 이미지를 만든다).
ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.12
# 기본값이 정식 이미지라 팀의 `docker compose build` 는 종전과 한 글자도 다르지 않다.
# Spark 배포만 여기에 런타임 이미지를 넣는다 (spark/compose.spark.yaml).
ARG BASE_IMAGE=apache/airflow:${AIRFLOW_VERSION}-python${PYTHON_VERSION}
FROM ${BASE_IMAGE}
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
