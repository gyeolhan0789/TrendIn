#!/bin/sh
# MinIO 초기화. compose 의 minio-init 서비스가 한 번 돌리며, 매 up 마다 다시 돌아도 결과가 같다.
# 하는 일: 버킷 생성 → 정책 두 개 등록 → 계정 두 개 생성 → 정책 연결.
# 크롤러는 write, Spark 는 read 로 나눈다 (Jira S15P21A102-156).
# minio/mc 이미지에는 sed 가 없다. 정책 JSON 은 여기서 직접 만든다.
set -eu

: "${MINIO_ENDPOINT:?}" "${MINIO_ROOT_USER:?}" "${MINIO_ROOT_PASSWORD:?}" "${MINIO_BUCKET:?}"
: "${MINIO_CRAWLER_ACCESS_KEY:?}" "${MINIO_CRAWLER_SECRET_KEY:?}"
: "${MINIO_SPARK_ACCESS_KEY:?}" "${MINIO_SPARK_SECRET_KEY:?}"

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

rm -rf "$WORK"
echo "minio-init: bucket=$MINIO_BUCKET crawler=$MINIO_CRAWLER_ACCESS_KEY(write) spark=$MINIO_SPARK_ACCESS_KEY(read)"
