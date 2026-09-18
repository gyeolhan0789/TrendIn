#!/usr/bin/env bash
# 이미지를 두 단계로 만든다. 아래가 런타임(JRE·pyspark·torch·GLiNER), 위가 우리 패키지다.
#
#   pipeline/spark/scripts/build-image.sh          # 런타임 + 배포 이미지
#   pipeline/spark/scripts/build-image.sh --gpu    # 거기에 CUDA 이미지까지 (개발 PC 전용)
#
# 컴포즈는 "이 서비스의 FROM 이 저 이미지다" 를 모른다. 그래서 한 번에 build 하면 런타임
# 이미지가 없는 첫 실행에서 실패한다. 순서를 여기서 강제한다.
#
# --- 1단계는 보통 몇 초에 끝난다 (2026-09-18) --------------------------------
# 런타임 이미지는 versions.sh 가 바뀔 때만 실제로 다시 만들어진다. src 를 아무리 고쳐도
# 그 아래 3.5 GB 는 캐시에 맞는다 — 상속 방향을 뒤집은 이유가 이것이다 (spark/Dockerfile).
# versions.sh 를 고친 날에는 1단계가 5~6분 걸리고, 그것이 정상이다.
#
# 기본 이미지 s15p21a102/pipeline:local 은 여기서 만들지 않는다. 배포 스택은 오버레이가
# 이미지를 배포 이미지로 갈아끼우므로 그것을 쓰지 않고, Spark 없이 쓰는 쪽은 종전대로
# `docker compose -f compose.yaml build` 로 만든다.
set -euo pipefail

gpu=0
case "${1:-}" in
  --gpu) gpu=1 ;;
  "") ;;
  *) echo "쓰는 법: $0 [--gpu]" >&2; exit 64 ;;
esac

HERE=$(cd "$(dirname "$0")" && pwd)
PIPELINE_DIR=$(cd "$HERE/../.." && pwd)
cd "$PIPELINE_DIR"

RUNTIME_IMAGE=s15p21a102/pipeline-runtime:local
SPARK_IMAGE=s15p21a102/pipeline-spark:local

total=$(( gpu ? 3 : 2 ))

# 런타임 이미지는 정식 Airflow 이미지를 직접 상속한다. 어느 버전을 상속할지는
# pipeline/Dockerfile 이 정하므로 여기서 읽어 넘긴다. 두 파일에 숫자를 따로 적어 두면
# 한쪽만 올린 날 두 이미지가 다른 Airflow 위에 서고, 그것은 런타임에야 드러난다.
airflow_version=$(sed -n 's/^ARG AIRFLOW_VERSION=//p' Dockerfile | head -1)
python_version=$(sed -n 's/^ARG PYTHON_VERSION=//p' Dockerfile | head -1)
if [ -z "$airflow_version" ] || [ -z "$python_version" ]; then
  echo "pipeline/Dockerfile 에서 ARG AIRFLOW_VERSION · PYTHON_VERSION 을 읽지 못했다" >&2
  exit 1
fi

echo "1/$total  런타임 이미지 $RUNTIME_IMAGE  (JRE · pyspark · torch · GLiNER)"
echo "         airflow ${airflow_version} · python ${python_version}"
docker build \
  --build-arg "AIRFLOW_VERSION=$airflow_version" \
  --build-arg "PYTHON_VERSION=$python_version" \
  -t "$RUNTIME_IMAGE" \
  -f spark/Dockerfile \
  spark

echo
echo "2/$total  배포 이미지 $SPARK_IMAGE  (런타임 + 우리 패키지)"
docker compose -f compose.yaml -f spark/compose.spark.yaml build airflow-scheduler

# 다 쌓은 뒤에 한 번 본다. 예전에는 이 검사가 이미지 안 마지막 RUN 이었는데, 우리 패키지가
# 맨 위로 올라오면서 그 자리가 런타임 이미지 안이 되어 kiwipiepy 를 볼 수 없다. 여기서
# 보면 층 순서와 무관하게 "다 깔린 이미지" 를 본다 — 우리 패키지를 깔면서 pip 이 Airflow
# constraints 를 맞추느라 torch 쪽 패키지를 내렸다면 그것도 여기서 걸린다.
echo
echo "     확인  import yaml, pyspark, gliner, kiwipiepy"
docker run --rm "$SPARK_IMAGE" \
  python -c "import yaml, pyspark, gliner, kiwipiepy; print('  ok  pyspark', pyspark.__version__)"

if [ "$gpu" -eq 1 ]; then
  echo
  echo "3/3  CUDA 이미지 s15p21a102/pipeline-spark-gpu:local  (torch 를 CUDA 휠로)"
  # **`build airflow-scheduler` 뿐이다.** airflow-cli 는 같은 이미지를 가리키므로 여기서
  # 또 빌드하면 같은 레이어를 두 번 읽는다 (2단계가 scheduler 만 빌드하는 것과 같은 이유).
  docker compose -f compose.yaml -f spark/compose.spark.yaml -f spark/compose.gpu.yaml \
    build airflow-scheduler
fi

echo
echo "끝. 띄우기:"
echo "  docker compose -f compose.yaml -f spark/compose.spark.yaml up -d"
if [ "$gpu" -eq 1 ]; then
  echo
  echo "GPU 로 추출하기 (spark/compose.gpu.yaml 의 머리말):"
  echo "  docker compose -f compose.yaml -f spark/compose.spark.yaml -f spark/compose.gpu.yaml \\"
  echo "    --profile debug run --rm --no-deps airflow-cli \\"
  echo "    bash -c 'spark/scripts/submit.sh extract --profile local --domain fashion --force'"
fi
