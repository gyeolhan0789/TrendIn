#!/usr/bin/env bash
# 받아둔 jar 가 실제로 물리는지 확인한다. 외부 서비스는 필요 없다.
#
#   spark/scripts/check-jars.sh
#
# 어긋난 조합은 보통 처음 Kafka 를 읽을 때 NoSuchMethodError 로 죽는데, 그때는 원인이
# jar 인지 코드인지 구분하기 어렵다. 여기서 먼저 갈라둔다.
set -euo pipefail

# shellcheck source=_common.sh
. "$(dirname "$0")/_common.sh"

SPARK_DIR=$(spark_dir)
PIPELINE_DIR=$(cd "$SPARK_DIR/.." && pwd)

jars=$(jar_list "$SPARK_DIR/jars")
resolve_python "$PIPELINE_DIR"
log4j=$(to_file_uri "$SPARK_DIR/conf/log4j2.properties")
script=$(to_app_uri "$SPARK_DIR/scripts/check-jars.py")

cd "$PIPELINE_DIR"
exec spark-submit \
  --jars "$jars" \
  --driver-java-options "-Dlog4j.configurationFile=$log4j" \
  "$script"
