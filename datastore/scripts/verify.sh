#!/bin/sh
# datastore 완료 조건 검증. 실패 항목이 있으면 exit 1.
# AC1~4 는 Jira S15P21A102-156, AC5 는 S15P21A102-157 (토픽 설정 · 보관 정책).
# Windows 는 Git Bash 에서 돌린다. 검증은 전부 컨테이너 안에서 일어난다.
set -u

# Git Bash 가 /opt/... 를 윈도우 경로로 바꾸는 것을 막는다. 절대 경로도 함께 막히므로
# 디렉터리로 옮겨 상대 경로만 쓴다.
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
cd "$(dirname "$0")/.." || exit 1
[ -f .env ] || { echo "datastore/.env 가 없다 — .env.example 을 복사해 채운다"; exit 1; }

DC="docker compose -f compose.yaml"
MC_IMAGE=minio/mc:RELEASE.2025-08-13T08-35-41Z
NET=s15p21a102-data
OBJ="_verify/$(date -u +%Y%m%dT%H%M%SZ).txt"
fail=0

BUCKET=$(sed -n 's/^MINIO_BUCKET=//p' .env);                  BUCKET=${BUCKET:-raw-data}
TOPIC=$(sed -n 's/^KAFKA_TOPIC_RAW_FILE_READY=//p' .env);     TOPIC=${TOPIC:-raw-file-ready}
PARTS=$(sed -n 's/^KAFKA_TOPIC_PARTITIONS=//p' .env);         PARTS=${PARTS:-6}
POLICY=$(sed -n 's/^KAFKA_TOPIC_CLEANUP_POLICY=//p' .env);    POLICY=${POLICY:-delete}
RET_MS=$(sed -n 's/^KAFKA_TOPIC_RETENTION_MS=//p' .env);      RET_MS=${RET_MS:-604800000}
SEG_MS=$(sed -n 's/^KAFKA_TOPIC_SEGMENT_MS=//p' .env);        SEG_MS=${SEG_MS:-86400000}
RAW_DAYS=$(sed -n 's/^MINIO_RAW_EXPIRE_DAYS=//p' .env);       RAW_DAYS=${RAW_DAYS:-90}
VFY_DAYS=$(sed -n 's/^MINIO_VERIFY_EXPIRE_DAYS=//p' .env);    VFY_DAYS=${VFY_DAYS:-1}
CK=$(sed -n 's/^MINIO_CRAWLER_ACCESS_KEY=//p' .env); CS=$(sed -n 's/^MINIO_CRAWLER_SECRET_KEY=//p' .env)
SK=$(sed -n 's/^MINIO_SPARK_ACCESS_KEY=//p' .env);   SS=$(sed -n 's/^MINIO_SPARK_SECRET_KEY=//p' .env)
RU=$(sed -n 's/^MINIO_ROOT_USER=//p' .env);          RP=$(sed -n 's/^MINIO_ROOT_PASSWORD=//p' .env)
[ -n "$CK$CS$SK$SS" ] || { echo "datastore/.env 의 MinIO 키가 비어 있다"; exit 1; }
[ -n "$RU$RP" ] || { echo "datastore/.env 의 MinIO 관리자 계정이 비어 있다"; exit 1; }

# 첫 인자가 0 이면 통과, 아니면 실패로 찍는다.
check() { [ "$1" -eq 0 ] && echo "  PASS  $2" || { echo "  FAIL  $2"; fail=1; }; }

# mc 를 저장소 네트워크 안에서 돌린다. crawler · spark 두 계정을 미리 물려둔다.
# admin 은 버킷 설정(버전 관리 · 수명 주기) 조회용이다. crawler · spark 정책에는 그 권한이 없다.
mc() {
  docker run --rm --network "$NET" \
    -e MC_HOST_crawler="http://$CK:$CS@minio:9000" \
    -e MC_HOST_spark="http://$SK:$SS@minio:9000" \
    -e MC_HOST_admin="http://$RU:$RP@minio:9000" \
    --entrypoint sh "$MC_IMAGE" -c "$1"
}

echo "[AC1] 컨테이너"
for svc in kafka minio; do
  cid=$($DC ps -q $svc 2>/dev/null)
  if [ -z "$cid" ]; then check 1 "$svc 가 떠 있지 않다"; continue; fi
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" = healthy ]; check $? "$svc healthy"
  [ "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$cid")" = unless-stopped ]; check $? "$svc restart=unless-stopped"
done
[ "$fail" -eq 0 ] || { echo "기동부터 실패. 나머지는 건너뛴다."; exit 1; }

echo "[AC2] 접속 경로"
docker network inspect "$NET" >/dev/null 2>&1; check $? "네트워크 $NET 존재"
for hp in kafka:9092 minio:9000; do
  docker run --rm --network "$NET" busybox:1.37 nc -z -w 3 "${hp%:*}" "${hp#*:}" >/dev/null 2>&1
  check $? "네트워크 안에서 $hp 도달"
done

echo "[AC3] Kafka"
$DC exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list 2>/dev/null | grep -qx "$TOPIC"
check $? "토픽 $TOPIC 존재"
printf '_verify:{"event_id":"_verify","status":"success","record_count":0}\n' \
  | $DC exec -T kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 \
      --topic "$TOPIC" --property parse.key=true --property key.separator=: >/dev/null 2>&1
check $? "produce"
$DC exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
    --topic "$TOPIC" --from-beginning --timeout-ms 20000 2>/dev/null | grep -q '_verify'
check $? "consume (발행한 메시지 회수)"

echo "[AC4] MinIO 권한 분리"
mc "echo verify > /tmp/v && mc cp /tmp/v crawler/$BUCKET/$OBJ" >/dev/null 2>&1
check $? "크롤러 키 put"
[ "$(mc "mc cat crawler/$BUCKET/$OBJ" 2>/dev/null | tr -d '\r\n')" = verify ]; check $? "크롤러 키 get"
[ "$(mc "mc cat spark/$BUCKET/$OBJ"   2>/dev/null | tr -d '\r\n')" = verify ]; check $? "Spark 키 get"
# 여기는 성공하면 안 된다. 성공하면 정책이 잘못 붙은 것이다.
if mc "echo x > /tmp/x && mc cp /tmp/x spark/$BUCKET/_verify/should-fail" >/dev/null 2>&1; then
  check 1 "Spark 키로 쓰기가 성공했다 — 정책을 확인한다"
else
  check 0 "Spark 키 write 거부"
fi

echo "[AC5] 토픽 설정"
PC=$($DC exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 \
      --describe --topic "$TOPIC" 2>/dev/null | tr -d '\r' \
      | sed -n 's/.*PartitionCount: \([0-9][0-9]*\).*/\1/p' | head -1)
[ "${PC:-0}" -eq "$PARTS" ]; check $? "파티션 $PARTS 개 (실제 ${PC:-?})"
CFG=$($DC exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server localhost:9092 \
      --entity-type topics --entity-name "$TOPIC" --describe 2>/dev/null | tr -d '\r')
for kv in "cleanup.policy=$POLICY" "retention.ms=$RET_MS" "segment.ms=$SEG_MS"; do
  printf '%s\n' "$CFG" | grep -q -- "$kv"; check $? "$kv"
done

echo "[AC5] 보관 정책"
# 규칙 조회는 버킷 설정 읽기 권한이 필요하다. 관리자 계정으로 본다.
ILM=$(mc "mc ilm rule ls admin/$BUCKET 2>/dev/null || mc ilm ls admin/$BUCKET" 2>/dev/null | tr -d '\r')
# 각각 정확히 1 개여야 한다. 2 개 이상이면 매 up 마다 규칙이 덧붙고 있다는 뜻이다.
[ "$(printf '%s\n' "$ILM" | grep -c 'expire-raw')" -eq 1 ];    check $? "lifecycle expire-raw 1 개"
[ "$(printf '%s\n' "$ILM" | grep -c 'expire-verify')" -eq 1 ]; check $? "lifecycle expire-verify 1 개 (중복 없음)"
mc "mc version info admin/$BUCKET" 2>/dev/null | grep -qiE 'un-versioned|suspended'
check $? "버전 관리 off"
# 원문이 이벤트보다 먼저 사라지면 참조가 깨진다. 등호 포함이라 같아도 통과다.
[ "$((RAW_DAYS * 86400000))" -ge "$RET_MS" ]
check $? "MinIO 보관 ${RAW_DAYS}일 >= Kafka retention ${RET_MS}ms"

# 검증 객체만 지운다. 수집 데이터는 건드리지 않는다.
mc "mc rm -r --force crawler/$BUCKET/_verify" >/dev/null 2>&1

[ "$fail" -eq 0 ] && { echo; echo "전부 통과."; exit 0; }
echo; echo "실패한 항목이 있다. 위 FAIL 을 확인한다."; exit 1
