#!/usr/bin/env bash
# 이미지를 두 단계로 만든다. 파생 이미지가 기본 이미지를 FROM 하기 때문이다.
#
#   pipeline/spark/scripts/build-image.sh          # 기본 + Spark 이미지
#   pipeline/spark/scripts/build-image.sh --gpu    # 거기에 CUDA 이미지까지 (개발 PC 전용)
#
# 컴포즈는 "이 서비스의 FROM 이 저 서비스의 image 다" 를 모른다. 그래서 한 번에
# build 하면 기본 이미지가 없는 첫 실행에서 실패한다. 순서를 여기서 강제한다.
#
# pipeline 이미지가 바뀌면(의존성 추가 등) 이 스크립트를 다시 돌려야 한다. 파생 이미지는
# 기본 이미지를 다시 읽지 않으면 옛 레이어 위에 그대로 있다.
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

total=$(( gpu ? 3 : 2 ))

echo "1/$total  기본 이미지 s15p21a102/pipeline:local"
docker compose -f compose.yaml build

echo
echo "2/$total  파생 이미지 s15p21a102/pipeline-spark:local  (JRE + pyspark)"
docker compose -f compose.yaml -f spark/compose.spark.yaml build airflow-scheduler

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
