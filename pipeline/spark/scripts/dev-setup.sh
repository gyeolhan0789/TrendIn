#!/usr/bin/env bash
# 로컬에서 Spark Job 을 호스트 .venv 로 돌리기 위한 준비. pyspark 설치 + jar 받기.
#
#   pipeline/scripts/dev-setup.sh          # 먼저 (Airflow · pytest · ruff)
#   pipeline/spark/scripts/dev-setup.sh    # 그다음 (Spark)
#
# 두 스크립트를 나눈 이유 — Spark 를 만지지 않는 사람이 pyspark 450 MB 와 jar 530 MB 를
# 받을 이유가 없다. 팀 공용 스크립트는 그대로 두고 여기만 추가로 돈다.
#
# 컨테이너에는 이 스크립트가 관여하지 않는다. spark/Dockerfile 이 같은 versions.sh 를
# 읽어 같은 버전을 넣는다.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PIPELINE_DIR=$(cd "$HERE/../.." && pwd)
cd "$PIPELINE_DIR"

# shellcheck source=../versions.sh
. "$HERE/../versions.sh"

AIRFLOW_VERSION=3.3.1
PYTHON_VERSION=3.12
CONSTRAINTS_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# .venv 는 팀 공용 스크립트가 만든다. 여기서 만들면 두 곳이 같은 것을 관리하게 된다.
if [ ! -d .venv ]; then
  echo "먼저 ./scripts/dev-setup.sh 를 돌려 .venv 를 만든다." >&2
  exit 1
fi

VENV_PYTHON=.venv/bin/python
[ -x "$VENV_PYTHON" ] || VENV_PYTHON=.venv/Scripts/python.exe

constraints=$(mktemp)
trap 'rm -f "$constraints"' EXIT
curl -sSfL "$CONSTRAINTS_URL" -o "$constraints"

# constraints 를 같이 거는 이유 — pyspark 자체는 py4j 만 필요하지만, 같은 가상환경의
# pandas·pyarrow 가 Airflow 핀에서 밀려나면 DAG 쪽이 조용히 깨진다.
uv pip install --python "$VENV_PYTHON" "pyspark==${SPARK_VERSION}" pyyaml --constraint "$constraints"

# 실체 인식 ([04 §2], `extract/entities.py`). torch 를 CPU 휠로 **먼저** 깐다 — 순서를
# 바꾸면 CUDA 런타임이 딸려와 가상환경이 3 GB 넘게 커진다. 건너뛰려면 SKIP_MODEL=1 이고,
# 그때는 층 1 테스트만 돈다 (층 2 의 추출 테스트가 모델을 부른다).
#
# **constraints 를 함께 건다.** gliner 는 transformers·huggingface-hub 를 끌고 오고 그것들이
# `fsspec` · `numpy` 처럼 Airflow 도 쓰는 패키지를 밀어 올린다. 걸지 않으면 같은 가상환경의
# DAG 쪽이 조용히 깨진다 — pyspark 설치에 constraints 를 건 것과 같은 이유다.
if [ "${SKIP_MODEL:-0}" != "1" ]; then
  uv pip install --python "$VENV_PYTHON" --index-url "$TORCH_CPU_INDEX" torch \
    --constraint "$constraints"
  uv pip install --python "$VENV_PYTHON" "gliner==${GLINER_VERSION}" --constraint "$constraints"
fi

# 530 MB 짜리 AWS SDK 번들이 있어 처음 한 번은 오래 걸린다. 건너뛰려면 SKIP_JARS=1.
if [ "${SKIP_JARS:-0}" != "1" ]; then
  "$HERE/fetch-jars.sh"
fi

echo
echo "준비 끝. pyspark ${SPARK_VERSION}"
echo "  테스트:  .venv/bin/pytest spark/tests"
echo "  실행:    spark/scripts/submit.sh ingest --profile local"
echo "  jar 정합: spark/scripts/check-jars.sh"
