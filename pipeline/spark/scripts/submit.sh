#!/usr/bin/env bash
# spark-submit 감싸개. jar 목록 · log4j · 드라이버 파이썬을 매번 손으로 적지 않게 한다.
#
#   spark/scripts/submit.sh ingest --profile local
#   spark/scripts/submit.sh aggregate --profile dev --date 2026-09-03
#
# 첫 인자는 Job 이름(ingest · extract · aggregate), 나머지는 그대로 Job 에 넘어간다.
# spark-submit 자체에 옵션을 더 주려면 SPARK_SUBMIT_OPTS_EXTRA 에 넣는다.
set -euo pipefail

# shellcheck source=_common.sh
. "$(dirname "$0")/_common.sh"

SPARK_DIR=$(spark_dir)
PIPELINE_DIR=$(cd "$SPARK_DIR/.." && pwd)

job=${1:-}
case "$job" in
  ingest|extract|aggregate) shift ;;
  *)
    echo "쓰는 법: $0 {ingest|extract|aggregate} [--profile local] ..." >&2
    exit 64
    ;;
esac

jars=$(jar_list "$SPARK_DIR/jars")
resolve_python "$PIPELINE_DIR"
log4j=$(to_file_uri "$SPARK_DIR/conf/log4j2.properties")

# Job 스크립트 경로도 URI 로 준다. Git Bash 는 POSIX 경로 인자를 네이티브 프로그램에
# 넘길 때 드라이브 표기로 자동 변환하는데, spark-submit 은 그 앞 글자를 URI 스킴으로
# 읽어 `No FileSystem for scheme "C"` 로 죽는다. file:/// 로 시작하면 변환도 안 걸린다.
job_file="$SPARK_DIR/jobs/$job.py"
if command -v cygpath >/dev/null 2>&1; then
  job_file=$(to_file_uri "$job_file")
fi

cd "$PIPELINE_DIR"
exec spark-submit \
  --jars "$jars" \
  --driver-java-options "-Dlog4j.configurationFile=$log4j" \
  ${SPARK_SUBMIT_OPTS_EXTRA:-} \
  "$job_file" "$@"
