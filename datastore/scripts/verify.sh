#!/bin/sh
# datastore 완료 조건 검증. 실패 항목이 있으면 exit 1.
# AC1~3 은 Jira S15P21A102-156, AC4 는 S15P21A102-158 (보관 정책).
# curated 버킷 쓰기 · 만료 없음은 S15P21A102-243.
# 토픽 검증은 브로커와 함께 걷혔다 (Kafka 제거 3/3).
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
CURATED=$(sed -n 's/^MINIO_CURATED_BUCKET=//p' .env);         CURATED=${CURATED:-curated}
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
cid=$($DC ps -q minio 2>/dev/null)
if [ -z "$cid" ]; then
  check 1 "minio 가 떠 있지 않다"
else
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$cid")" = healthy ]; check $? "minio healthy"
  [ "$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "$cid")" = unless-stopped ]; check $? "minio restart=unless-stopped"
fi
[ "$fail" -eq 0 ] || { echo "기동부터 실패. 나머지는 건너뛴다."; exit 1; }

echo "[AC2] 접속 경로"
docker network inspect "$NET" >/dev/null 2>&1; check $? "네트워크 $NET 존재"
docker run --rm --network "$NET" busybox:1.37 nc -z -w 3 minio 9000 >/dev/null 2>&1
check $? "네트워크 안에서 minio:9000 도달"

echo "[AC3] MinIO 권한 분리"
mc "echo verify > /tmp/v && mc cp /tmp/v crawler/$BUCKET/$OBJ" >/dev/null 2>&1
check $? "크롤러 키 put"
[ "$(mc "mc cat crawler/$BUCKET/$OBJ" 2>/dev/null | tr -d '\r\n')" = verify ]; check $? "크롤러 키 get"
[ "$(mc "mc cat spark/$BUCKET/$OBJ"   2>/dev/null | tr -d '\r\n')" = verify ]; check $? "Spark 키 get"
# 여기는 성공하면 안 된다. 성공하면 정책이 잘못 붙은 것이다.
# raw-data 는 원문이고 Spark 는 읽기만 한다. 아래 curated 검증과 짝이다 — 한쪽만 보면
# 정책이 두 버킷에 통으로 붙은 사고를 잡지 못한다.
if mc "echo x > /tmp/x && mc cp /tmp/x spark/$BUCKET/_verify/should-fail" >/dev/null 2>&1; then
  check 1 "Spark 키로 $BUCKET 쓰기가 성공했다 — 정책을 확인한다"
else
  check 0 "Spark 키 $BUCKET write 거부"
fi

# curated 는 반대다. ingest 가 정제 결과를 쓰고 extract 가 읽으므로 put · get 이 되어야 하고,
# 파티션 덮어쓰기(mode=overwrite + partitionOverwriteMode=dynamic)가 옛 part 파일을 지우므로
# delete 도 되어야 한다. 셋 중 하나라도 막히면 ingest 가 첫 실행이나 첫 재처리에서 죽는다.
mc "echo verify > /tmp/v && mc cp /tmp/v spark/$CURATED/$OBJ" >/dev/null 2>&1
check $? "Spark 키 $CURATED put"
[ "$(mc "mc cat spark/$CURATED/$OBJ" 2>/dev/null | tr -d '\r\n')" = verify ]; check $? "Spark 키 $CURATED get"
mc "mc rm spark/$CURATED/$OBJ" >/dev/null 2>&1
check $? "Spark 키 $CURATED delete"

echo "[AC4] 보관 정책"
# 규칙 조회는 버킷 설정 읽기 권한이 필요하다. 관리자 계정으로 본다.
ILM=$(mc "mc ilm rule ls admin/$BUCKET 2>/dev/null || mc ilm ls admin/$BUCKET" 2>/dev/null | tr -d '\r')
# 정확히 1 개여야 한다. 2 개 이상이면 매 up 마다 규칙이 덧붙고 있다는 뜻이다.
# 접두어를 보지 않는 규칙 하나라 키 규칙이 바뀌어도 어긋나지 않는다 (S15P21A102-158).
[ "$(printf '%s\n' "$ILM" | grep -c 'expire-all')" -eq 1 ]; check $? "lifecycle expire-all 1 개 (중복 없음)"
mc "mc version info admin/$BUCKET" 2>/dev/null | grep -qiE 'un-versioned|suspended'
check $? "버전 관리 off"
# curated 에는 만료 규칙이 없어야 한다 (S15P21A102-243). raw-data 는 90 일 뒤 지워도 되는
# 수집 원문이지만 curated 는 extract 가 계속 읽는 정제 결과다. 만료를 걸면 옛 ingest_run_id
# 파티션부터 사라져 재집계와 백필이 조용히 빈 구간을 만든다.
# 규칙이 하나도 없으면 mc 가 실패하고 출력이 빈다. 'Enabled' 가 보이는 경우만 잡는다.
CILM=$(mc "mc ilm rule ls admin/$CURATED 2>/dev/null || mc ilm ls admin/$CURATED" 2>/dev/null | tr -d '\r')
if printf '%s\n' "$CILM" | grep -q 'Enabled'; then
  check 1 "$CURATED 에 수명 주기 규칙이 붙어 있다 — 정제 결과는 만료되면 안 된다"
else
  check 0 "$CURATED 수명 주기 없음"
fi
mc "mc version info admin/$CURATED" 2>/dev/null | grep -qiE 'un-versioned|suspended'
check $? "$CURATED 버전 관리 off"

# 검증 객체만 지운다. 수집 데이터는 건드리지 않는다.
# 크롤러 키에는 삭제 권한이 없다. 관리자 키로 지운다 — 크롤러 키로 하면 조용히
# 실패하고 객체가 수명 주기(90 일)까지 남는다.
mc "mc rm -r --force admin/$BUCKET/_verify" >/dev/null 2>&1
# curated 에는 수명 주기가 없어 남으면 영영 남는다. 위 delete 검증이 실패한 경우를 대비해
# 관리자 키로 한 번 더 지운다.
mc "mc rm -r --force admin/$CURATED/_verify" >/dev/null 2>&1

[ "$fail" -eq 0 ] && { echo; echo "전부 통과."; exit 0; }
echo; echo "실패한 항목이 있다. 위 FAIL 을 확인한다."; exit 1
