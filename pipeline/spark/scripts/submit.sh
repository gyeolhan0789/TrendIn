#!/usr/bin/env bash
# spark-submit 감싸개. jar 목록 · log4j · 드라이버 파이썬을 매번 손으로 적지 않게 한다.
#
#   spark/scripts/submit.sh ingest --profile local
#   spark/scripts/submit.sh aggregate --profile dev --date 2026-09-03
#
# 첫 인자는 Job 이름(ingest · extract · concept · aggregate · analyze), 나머지는 그대로 Job 에 넘어간다.
# spark-submit 자체에 옵션을 더 주려면 SPARK_SUBMIT_OPTS_EXTRA 에, 드라이버 힙만 바꾸려면
# SPARK_DRIVER_MEMORY 에 넣는다.
set -euo pipefail

# shellcheck source=_common.sh
. "$(dirname "$0")/_common.sh"

SPARK_DIR=$(spark_dir)
PIPELINE_DIR=$(cd "$SPARK_DIR/.." && pwd)

job=${1:-}
case "$job" in
  ingest|extract|concept|aggregate|analyze) shift ;;
  *)
    echo "쓰는 법: $0 {ingest|extract|concept|aggregate|analyze} [--profile local] ..." >&2
    exit 64
    ;;
esac

jars=$(jar_list "$SPARK_DIR/jars")
resolve_python "$PIPELINE_DIR"
log4j=$(to_file_uri "$SPARK_DIR/conf/log4j2.properties")

# Job 스크립트 경로도 URI 로 준다 (이유는 `_common.sh` 의 `to_app_uri`).
job_file=$(to_app_uri "$SPARK_DIR/jobs/$job.py")

# 드라이버 힙. **Spark 기본값 1GB 로는 `ingest` 가 못 돈다** — curated 를 쓴 뒤 파티션을
# 훑는 자리(`InMemoryFileIndex.partitionSpec`)에서 힙이 터진다. 2026-09-18 에 15회 연속
# OOM 으로 죽어 적재가 하루 멈췄고, 증상은 "트렌드 화면이 비었다" 로만 보였다.
#
# 여기 두는 이유는 로컬·dev·운영이 같은 값으로 돌아야 하기 때문이다. 컴포즈의 environment
# 에 두면 dev 배포에만 걸리고 로컬에서 같은 방식으로 다시 죽는다.
#
# `local[*]` 이라 드라이버가 곧 실행기라서 이 값 하나가 Job 전부에 걸리지만, 상한일 뿐
# 미리 잡지 않으므로 가벼운 Job 이 손해 보지 않는다.
: "${SPARK_DRIVER_MEMORY:=4g}"

cd "$PIPELINE_DIR"
exec spark-submit \
  --jars "$jars" \
  --driver-memory "$SPARK_DRIVER_MEMORY" \
  --driver-java-options "-Dlog4j.configurationFile=$log4j" \
  ${SPARK_SUBMIT_OPTS_EXTRA:-} \
  "$job_file" "$@"
