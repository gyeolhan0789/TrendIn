#!/usr/bin/env bash
# 런타임 jar 를 Maven Central 에서 받아 spark/jars/ 에 둔다. 버전은 spark/versions.sh 가 정한다.
#
#   pipeline/spark/scripts/fetch-jars.sh
#
# --packages 로 런타임에 받지 않는 이유 (09 §2): 매 실행마다 네트워크를 타고,
# 오프라인이면 죽고, 이행 의존성이 조용히 바뀔 수 있다.
#
# 받은 jar 는 컨테이너에 굽지 않고 읽기 전용으로 마운트한다 (spark/compose.spark.yaml).
# 530 MB 를 이미지 레이어에 넣으면 jar 하나 바뀔 때마다 이미지를 다시 만들어야 한다.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
DEST=$HERE/../jars

# shellcheck source=../versions.sh
. "$HERE/../versions.sh"

REPO=https://repo1.maven.org/maven2

# group/artifact/version — 이 목록이 곧 --jars 에 들어가는 전부다.
JARS=(
  "org.apache.spark/spark-sql-kafka-0-10_${SCALA_BINARY}/${SPARK_VERSION}"
  "org.apache.spark/spark-token-provider-kafka-0-10_${SCALA_BINARY}/${SPARK_VERSION}"
  "org.apache.kafka/kafka-clients/${KAFKA_CLIENTS}"
  "org.apache.commons/commons-pool2/${COMMONS_POOL2}"
  "org.apache.hadoop/hadoop-aws/${HADOOP_VERSION}"
  # S3A 가 AWS SDK v2 를 쓰기 시작한 hadoop 3.4 부터는 이 통짜 번들이 표준 조합이다.
  # 모듈을 쪼개 받으면 이행 의존성을 손으로 맞춰야 한다.
  "software.amazon.awssdk/bundle/${AWS_SDK_VERSION}"
  "org.postgresql/postgresql/${POSTGRES_JDBC}"
)

mkdir -p "$DEST"

for coord in "${JARS[@]}"; do
  group=${coord%%/*}
  rest=${coord#*/}
  artifact=${rest%%/*}
  version=${rest#*/}
  file="${artifact}-${version}.jar"
  path="${group//./\/}/${artifact}/${version}/${file}"

  if [ -f "$DEST/$file" ]; then
    echo "있음  $file"
    continue
  fi

  echo "받음  $file"
  # 받다 끊긴 파일이 "있음" 으로 남지 않게 임시 이름으로 받고 옮긴다.
  curl -fSL --retry 3 "$REPO/$path" -o "$DEST/.$file.part"
  mv "$DEST/.$file.part" "$DEST/$file"
done

# 옛 버전이 남아 있으면 --jars 가 둘 다 집어 클래스패스가 갈린다.
stale=0
for existing in "$DEST"/*.jar; do
  [ -e "$existing" ] || continue
  name=$(basename "$existing")
  keep=no
  for coord in "${JARS[@]}"; do
    rest=${coord#*/}
    if [ "$name" = "${rest%%/*}-${rest#*/}.jar" ]; then
      keep=yes
      break
    fi
  done
  if [ "$keep" = no ]; then
    echo "남음  $name — 목록에 없다. 지워야 클래스패스가 갈리지 않는다" >&2
    stale=1
  fi
done

echo
echo "받은 곳: $(cd "$DEST" && pwd)"
echo "쓰는 법: spark/scripts/submit.sh ingest --profile local   (호스트 .venv)"
echo "         컨테이너에서는 spark/compose.spark.yaml 이 이 디렉터리를 마운트한다"
[ "$stale" = 0 ] || exit 1
