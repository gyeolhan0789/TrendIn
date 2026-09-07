#!/bin/sh
# MinIO 초기화. compose 의 minio-init 서비스가 한 번 돌리며, 매 up 마다 다시 돌아도 결과가 같다.
# 하는 일: 버킷 생성 → 정책 두 개 등록 → 계정 두 개 생성 → 정책 연결 → 버전 관리 · 수명 주기 적용.
# 크롤러는 write, Spark 는 read 로 나눈다 (Jira S15P21A102-156).
# 보관 정책은 Jira S15P21A102-157. 값과 근거는 datastore/README.md "보관 정책" 절.
# minio/mc 이미지에는 sed 가 없다. 정책 JSON 은 여기서 직접 만든다.
set -eu

: "${MINIO_ENDPOINT:?}" "${MINIO_ROOT_USER:?}" "${MINIO_ROOT_PASSWORD:?}" "${MINIO_BUCKET:?}"
: "${MINIO_CRAWLER_ACCESS_KEY:?}" "${MINIO_CRAWLER_SECRET_KEY:?}"
: "${MINIO_SPARK_ACCESS_KEY:?}" "${MINIO_SPARK_SECRET_KEY:?}"
: "${MINIO_RAW_PREFIX:?}" "${MINIO_RAW_EXPIRE_DAYS:?}" "${MINIO_VERIFY_EXPIRE_DAYS:?}"

WORK=/tmp/minio-init
mkdir -p "$WORK"

mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc ready local

# 버킷. 이미 있으면 넘어간다. 익명 접근은 명시적으로 닫는다.
mc mb --ignore-existing "local/$MINIO_BUCKET"
mc anonymous set none "local/$MINIO_BUCKET" >/dev/null

# 크롤러: 원문을 올린다. 삭제 권한은 주지 않는다.
cat > "$WORK/crawler-write.json" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET/*"]
    }
  ]
}
JSON

# Spark: 원문을 읽기만 한다.
cat > "$WORK/spark-read.json" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::$MINIO_BUCKET/*"]
    }
  ]
}
JSON

# create 는 같은 이름이 있으면 내용을 덮어쓴다.
mc admin policy create local crawler-write "$WORK/crawler-write.json"
mc admin policy create local spark-read "$WORK/spark-read.json"

# add 는 이미 있는 계정이면 비밀키를 갱신한다.
mc admin user add local "$MINIO_CRAWLER_ACCESS_KEY" "$MINIO_CRAWLER_SECRET_KEY"
mc admin user add local "$MINIO_SPARK_ACCESS_KEY" "$MINIO_SPARK_SECRET_KEY"

# 이미 붙어 있으면 "already in effect" 로 실패한다. 그 경우만 넘어간다.
attach() {
  if err=$(mc admin policy attach local "$1" --user "$2" 2>&1); then
    return 0
  fi
  case "$err" in
    *"already in effect"*|*"already attached"*) return 0 ;;
    *) echo "$err" >&2; return 1 ;;
  esac
}

attach crawler-write "$MINIO_CRAWLER_ACCESS_KEY"
attach spark-read "$MINIO_SPARK_ACCESS_KEY"

# 버전 관리는 쓰지 않는다. 같은 run_id 재실행이 같은 경로를 덮어쓰는 구조라
# (설계문서 5장 멱등) 켜두면 재시도마다 옛 버전이 쌓여 용량만 는다.
# 누가 콘솔에서 켰으면 여기서 도로 끈다. suspend 는 이미 쌓인 버전을 지우지 않는다.
# 이미지에 grep 이 없다. 문자열 판정은 셸 내장 case 로 한다.
VSTATE=$(mc version info "local/$MINIO_BUCKET" 2>/dev/null || echo "")
case "$VSTATE" in
  *un-versioned*|*suspended*|*Suspended*|"")
    : ;;                       # 꺼져 있음. 또는 조회 실패 — 건드리지 않는다.
  *)
    echo "minio-init: 버전 관리가 켜져 있다 — suspend 로 되돌린다" >&2
    mc version suspend "local/$MINIO_BUCKET" >/dev/null ;;
esac

# 수명 주기. 만료 기준은 경로의 collected_date 가 아니라 객체 업로드 시각이다.
# 백필로 과거분을 지금 올려도 올린 날부터 센다.
# 두 규칙의 prefix 는 겹치지 않는다 — 겹치면 어느 만료가 이기는지 모호해진다.
cat > "$WORK/lifecycle.json" <<JSON
{
  "Rules": [
    {
      "ID": "expire-raw",
      "Status": "Enabled",
      "Filter": { "Prefix": "$MINIO_RAW_PREFIX" },
      "Expiration": { "Days": $MINIO_RAW_EXPIRE_DAYS }
    },
    {
      "ID": "expire-verify",
      "Status": "Enabled",
      "Filter": { "Prefix": "_verify/" },
      "Expiration": { "Days": $MINIO_VERIFY_EXPIRE_DAYS }
    }
  ]
}
JSON

# import 는 규칙 목록을 통째로 갈아끼운다. rule add 는 부를 때마다 새 ID 로 하나씩
# 덧붙어 매 up 마다 중복이 쌓이므로 쓰지 않는다.
# mc 버전에 따라 하위 명령 위치가 다르다. 새 이름을 먼저 시도한다.
if ! mc ilm rule import "local/$MINIO_BUCKET" < "$WORK/lifecycle.json" 2>/dev/null; then
  mc ilm import "local/$MINIO_BUCKET" < "$WORK/lifecycle.json"
fi

rm -rf "$WORK"
echo "minio-init: bucket=$MINIO_BUCKET crawler=$MINIO_CRAWLER_ACCESS_KEY(write) spark=$MINIO_SPARK_ACCESS_KEY(read)"
echo "minio-init: versioning=off lifecycle=${MINIO_RAW_PREFIX}:${MINIO_RAW_EXPIRE_DAYS}d _verify/:${MINIO_VERIFY_EXPIRE_DAYS}d"
