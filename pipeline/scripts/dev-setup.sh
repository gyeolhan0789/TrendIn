#!/usr/bin/env bash
# 로컬 가상환경(.venv)을 만들고 이미지와 같은 Airflow constraints 로 설치한다.
# 단위 테스트와 DagBag import 테스트는 이 환경에서 돈다. DAG 실행 검증은 컨테이너 안에서 한다.
set -euo pipefail
cd "$(dirname "$0")/.."

AIRFLOW_VERSION=3.3.1
PYTHON_VERSION=3.12
CONSTRAINTS_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

constraints=$(mktemp)
trap 'rm -f "$constraints"' EXIT
curl -sSfL "$CONSTRAINTS_URL" -o "$constraints"

uv venv --python "$PYTHON_VERSION" .venv
uv pip install --python .venv/bin/python -e ".[dev]" --constraint "$constraints"

echo
echo "준비 끝. 활성화: source .venv/bin/activate   테스트: pytest"
