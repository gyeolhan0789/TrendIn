#!/usr/bin/env bash
# 이미지를 두 단계로 만든다. 파생 이미지가 기본 이미지를 FROM 하기 때문이다.
#
#   pipeline/spark/scripts/build-image.sh
#
# 컴포즈는 "이 서비스의 FROM 이 저 서비스의 image 다" 를 모른다. 그래서 한 번에
# build 하면 기본 이미지가 없는 첫 실행에서 실패한다. 순서를 여기서 강제한다.
#
# pipeline 이미지가 바뀌면(의존성 추가 등) 이 스크립트를 다시 돌려야 한다. 파생 이미지는
# 기본 이미지를 다시 읽지 않으면 옛 레이어 위에 그대로 있다.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PIPELINE_DIR=$(cd "$HERE/../.." && pwd)
cd "$PIPELINE_DIR"

echo "1/2  기본 이미지 s15p21a102/pipeline:local"
docker compose -f compose.yaml build

echo
echo "2/2  파생 이미지 s15p21a102/pipeline-spark:local  (JRE + pyspark)"
docker compose -f compose.yaml -f spark/compose.spark.yaml build airflow-scheduler

echo
echo "끝. 띄우기:"
echo "  docker compose -f compose.yaml -f spark/compose.spark.yaml up -d"
