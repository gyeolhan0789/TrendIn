# submit.sh · check-jars.sh 가 함께 쓰는 것. 직접 실행하지 않는다.

spark_dir() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

# 받아둔 jar 를 쉼표 하나로 묶어 표준출력에 낸다. 비어 있으면 죽는다.
#
# 글롭(`--jars "spark/jars/*"`)을 쓰지 않는 이유 — Windows/Git Bash 에서
# `No main class set in JAR` 로 죽는 것을 확인했다. 쉼표 목록은 Spark 문서가 정의한
# 형식이라 어디서나 확실하다.
#
# Git Bash 의 /c/... 경로는 JVM 이 못 읽으므로 cygpath 가 있으면 거친다.
#
# 변환만으로는 부족하고 `file:///` 까지 붙여야 한다. `C:/Users/...` 를 그대로 주면
# spark-submit 이 `C:` 를 **URI 스킴**으로 읽어 세션이 뜨기도 전에 죽는다:
#
#     org.apache.hadoop.fs.UnsupportedFileSystemException: No FileSystem for scheme "C"
#
# 리눅스 경로(`/opt/...`)는 스킴이 없어 이 문제가 없으므로 그대로 둔다.
jar_list() {
  local dir=$1 jar sep=""
  if ! ls "$dir"/*.jar >/dev/null 2>&1; then
    echo "$dir 가 비어 있다. 먼저 spark/scripts/fetch-jars.sh 를 돌린다." >&2
    return 1
  fi
  for jar in "$dir"/*.jar; do
    if command -v cygpath >/dev/null 2>&1; then
      jar="file:///$(cygpath -m "$jar")"
    fi
    printf '%s%s' "$sep" "$jar"
    sep=","
  done
}

# 드라이버 파이썬을 PATH 운에 맡기지 않는다. 이게 .venv 의 것이 아니면 워커와 버전이
# 갈려 첫 UDF 에서 PYTHON_VERSION_MISMATCH 로 죽는다. 워커 쪽은 코드가 맞춘다
# (trendin.spark.common.session.ensure_worker_python).
resolve_python() {
  local pipeline_dir=$1 candidate
  local candidates=(
    "$pipeline_dir/.venv/bin/python"
    "$pipeline_dir/.venv/Scripts/python.exe"
    "$(command -v python3 || true)"
    "$(command -v python || true)"
  )
  if [ -z "${PYSPARK_PYTHON:-}" ]; then
    # 실행 비트만 보지 않고 실제로 한 번 돌려본다. 윈도우에서 만든 .venv 를 리눅스에
    # 마운트하면 Scripts/python.exe 가 -x 로는 통과하고 exec 에서 죽는다.
    for candidate in "${candidates[@]}"; do
      if [ -n "$candidate" ] && "$candidate" -c "" >/dev/null 2>&1; then
        export PYSPARK_PYTHON=$candidate
        break
      fi
    done
  fi
  if [ -z "${PYSPARK_PYTHON:-}" ]; then
    echo "쓸 수 있는 파이썬을 못 찾았다. .venv 를 만들거나 PYSPARK_PYTHON 을 직접 준다." >&2
    return 1
  fi
  export PYSPARK_DRIVER_PYTHON=${PYSPARK_DRIVER_PYTHON:-$PYSPARK_PYTHON}
}

# log4j 는 -Dlog4j.configurationFile 에 **URI** 를 원한다. 리눅스에서는 file:// + 절대경로면
# 되지만, Git Bash 의 /c/... 경로를 그대로 주면 JVM 이 못 읽고 조용히 기본 설정으로 돌아간다
# (로그에 "Reconfiguration failed ... at 'null'" 만 남는다). 그래서 변환을 거친다.
to_file_uri() {
  local path=$1
  if command -v cygpath >/dev/null 2>&1; then
    echo "file:///$(cygpath -m "$path")"
  else
    echo "file://$path"
  fi
}
