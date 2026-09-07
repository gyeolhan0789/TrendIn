#!/bin/sh
# Kafka 초기화. compose 의 kafka-init 서비스가 한 번 돌리며, 매 up 마다 다시 돌아도 결과가 같다.
# 하는 일: 토픽 생성 → 파티션 수 수렴 → 보존 설정 적용.
# 값과 근거: datastore/README.md "토픽 설정" 절 (Jira S15P21A102-157).
#
# 이 컨테이너는 이미지 기본 entrypoint 를 쓰지 않는다. 그래서 아래 KAFKA_* 환경변수가
# server.properties 로 번역되지 않는다. 브로커 설정이 아니라 이 스크립트의 입력값이다.
set -eu

: "${KAFKA_BOOTSTRAP:?}" "${KAFKA_TOPIC_RAW_FILE_READY:?}" "${KAFKA_TOPIC_PARTITIONS:?}"
: "${KAFKA_TOPIC_RETENTION_MS:?}" "${KAFKA_TOPIC_SEGMENT_MS:?}" "${KAFKA_TOPIC_CLEANUP_POLICY:?}"

BIN=/opt/kafka/bin
TOPIC=$KAFKA_TOPIC_RAW_FILE_READY
WANT=$KAFKA_TOPIC_PARTITIONS

# 없으면 만든다. 이미 있으면 조용히 넘어간다 — 이 경우 파티션 수는 옛날 값 그대로다.
"$BIN/kafka-topics.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" \
  --create --if-not-exists \
  --topic "$TOPIC" \
  --partitions "$WANT" \
  --replication-factor 1

# 그래서 실제 값을 다시 읽어 맞춘다.
# describe 첫 줄: Topic: raw-file-ready\tTopicId: ...\tPartitionCount: 6\t...
HAVE=$("$BIN/kafka-topics.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" --describe --topic "$TOPIC" \
  | sed -n 's/.*PartitionCount: \([0-9][0-9]*\).*/\1/p' | head -1)
[ -n "$HAVE" ] || { echo "kafka-init: 파티션 수를 읽지 못했다" >&2; exit 1; }

if [ "$HAVE" -lt "$WANT" ]; then
  # 늘리면 key 해시 매핑이 바뀐다. 이미 쌓인 메시지는 옛 파티션에 남아
  # retention 기간 동안 같은 key 가 두 파티션에 흩어진다. 그 뒤 정상화된다.
  echo "kafka-init: 파티션 $HAVE -> $WANT 로 늘린다"
  "$BIN/kafka-topics.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" \
    --alter --topic "$TOPIC" --partitions "$WANT"
elif [ "$HAVE" -gt "$WANT" ]; then
  # 카프카는 파티션을 줄이지 못한다. 토픽을 지우고 다시 만드는 수밖에 없으므로 여기서 멈추지 않는다.
  echo "kafka-init: 파티션이 $HAVE 개다. 설정값 $WANT 보다 많아 줄일 수 없다 — 그대로 둔다" >&2
fi

# 토픽 레벨 설정. 같은 값을 다시 넣어도 결과가 같다.
# 브로커 기본값(KAFKA_LOG_RETENTION_HOURS)보다 여기가 우선한다.
"$BIN/kafka-configs.sh" --bootstrap-server "$KAFKA_BOOTSTRAP" \
  --entity-type topics --entity-name "$TOPIC" \
  --alter --add-config "cleanup.policy=$KAFKA_TOPIC_CLEANUP_POLICY,retention.ms=$KAFKA_TOPIC_RETENTION_MS,segment.ms=$KAFKA_TOPIC_SEGMENT_MS"

echo "kafka-init: topic=$TOPIC partitions=$WANT cleanup.policy=$KAFKA_TOPIC_CLEANUP_POLICY retention.ms=$KAFKA_TOPIC_RETENTION_MS segment.ms=$KAFKA_TOPIC_SEGMENT_MS"
