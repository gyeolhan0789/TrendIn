#!/bin/sh
# MinIO 초기화. compose 의 minio-init 서비스가 한 번 돌리며, 매 up 마다 다시 돌아도 결과가 같다.
# 하는 일: 버킷 두 개 생성 → 정책 두 개 등록 → 계정 두 개 생성 → 정책 연결 → 버전 관리 · 수명 주기 적용.
# 크롤러는 raw-data 에 write, Spark 는 raw-data 를 read 하고 curated 에 write 한다
# (Jira S15P21A102-156 · S15P21A102-243).
# 보관 정책은 Jira S15P21A102-157 · S15P21A102-158. 값과 근거는 datastore/README.md "보관 정책" 절.
# minio/mc 이미지에는 sed 가 없다. 정책 JSON 은 여기서 직접 만든다.
set -eu

: "${MINIO_ENDPOINT:?}" "${MINIO_ROOT_USER:?}" "${MINIO_ROOT_PASSWORD:?}" "${MINIO_BUCKET:?}"
: "${MINIO_CURATED_BUCKET:?}"
: "${MINIO_CRAWLER_ACCESS_KEY:?}" "${MINIO_CRAWLER_SECRET_KEY:?}"
: "${MINIO_SPARK_ACCESS_KEY:?}" "${MINIO_SPARK_SECRET_KEY:?}"
: "${MINIO_RAW_EXPIRE_DAYS:?}"

WORK=/tmp/minio-init
mkdir -p "$WORK"

mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc ready local

# 버킷 둘. 이미 있으면 넘어간다. 익명 접근은 명시적으로 닫는다.
# raw-data 는 크롤러가 올리는 수집 원문이고, curated 는 Spark 의 ingest 가 쓰고 extract 가
# 읽는 정제 결과다 (pipeline/spark/docs/01-architecture.md 3장).
for bucket in "$MINIO_BUCKET" "$MINIO_CURATED_BUCKET"; do
  mc mb --ignore-existing "local/$bucket"
  mc anonymous set none "local/$bucket" >/dev/null
done

# 크롤러: 원문을 올린다. 삭제 권한은 주지 않는다. curated 에는 접근하지 않는다.
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

# Spark: 원문(raw-data)은 읽기만 하고, 정제 결과(curated)에는 쓴다.
#
# curated 쪽에 삭제 권한이 들어가는 이유는 쓰기 방식 때문이다. ingest 는
# mode("overwrite") + partitionOverwriteMode=dynamic 으로 Parquet 을 쓴다
# (pipeline/src/trendin/spark/normalize/curated.py). 그러면 같은 ingest_run_id 로
# 재처리할 때 그 파티션의 옛 part 파일을 지우고 새로 쓴다. 멀티파트와 _temporary
# 정리도 같은 권한을 쓴다. DeleteObject 가 없으면 첫 재처리에서 죽는다.
#
# raw-data 쪽에는 쓰기도 삭제도 주지 않는다. 원문은 Spark 가 건드릴 것이 아니다.
cat > "$WORK/spark-raw-read-curated-write.json" <<JSON
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
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:ListBucketMultipartUploads", "s3:GetBucketLocation"],
      "Resource": ["arn:aws:s3:::$MINIO_CURATED_BUCKET"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
      "Resource": ["arn:aws:s3:::$MINIO_CURATED_BUCKET/*"]
    }
  ]
}
JSON

# create 는 같은 이름이 있으면 내용을 덮어쓴다.
mc admin policy create local crawler-write "$WORK/crawler-write.json"
mc admin policy create local spark-raw-read-curated-write "$WORK/spark-raw-read-curated-write.json"

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
attach spark-raw-read-curated-write "$MINIO_SPARK_ACCESS_KEY"

# 이름이 바뀌기 전의 spark-read 를 걷어낸다. 새 이름을 붙인 뒤라 권한이 빈 순간이 없다.
# 이미 돌던 서버에만 남아 있고 새로 세우는 서버에는 없으므로, 없어도 실패로 보지 않는다.
# 남겨두면 계정에 정책이 둘 붙어 "Spark 는 읽기만" 이라는 옛 이름이 계속 보인다.
mc admin policy detach local spark-read --user "$MINIO_SPARK_ACCESS_KEY" >/dev/null 2>&1 || true
mc admin policy rm local spark-read >/dev/null 2>&1 || true

# 버전 관리는 두 버킷 모두 쓰지 않는다. 같은 run_id 재실행이 같은 경로를 덮어쓰는 구조라
# (설계문서 5장 멱등, curated 는 파티션 덮어쓰기) 켜두면 재시도마다 옛 버전이 쌓여 용량만 는다.
# 누가 콘솔에서 켰으면 여기서 도로 끈다. suspend 는 이미 쌓인 버전을 지우지 않는다.
# 이미지에 grep 이 없다. 문자열 판정은 셸 내장 case 로 한다.
suspend_versioning() {
  vstate=$(mc version info "local/$1" 2>/dev/null || echo "")
  case "$vstate" in
    *un-versioned*|*suspended*|*Suspended*|"")
      : ;;                     # 꺼져 있음. 또는 조회 실패 — 건드리지 않는다.
    *)
      echo "minio-init: $1 의 버전 관리가 켜져 있다 — suspend 로 되돌린다" >&2
      mc version suspend "local/$1" >/dev/null ;;
  esac
}

suspend_versioning "$MINIO_BUCKET"
suspend_versioning "$MINIO_CURATED_BUCKET"

# 수명 주기. 만료 기준은 경로의 발행일이 아니라 객체 업로드 시각이다.
# 백필로 과거분을 지금 올려도 올린 날부터 센다.
#
# 규칙은 하나고 접두어를 보지 않는다 (S15P21A102-158). 버킷에 들어오는 것이 전부 수집
# 원문이고 만료 기간도 하나라, 접두어로 가르면 키 규칙이 바뀔 때마다 규칙이 어긋난다 —
# 실제로 "domain=" 접두를 잡고 있었는데 키가 "fashion/..." 로 시작해 아무것도 매칭되지
# 않았다. 규칙은 유효하고 대상만 0 개라 에러도 나지 않는다.
# verify.sh 가 남기는 _verify/ 객체도 같이 90 일을 산다. 7 바이트짜리 텍스트라 규칙을
# 하나 더 두는 값이 없다.
#
# **curated 에는 걸지 않는다** (S15P21A102-243). 거기 있는 것은 원문이 아니라 extract 가
# 계속 읽는 정제 결과다. 만료를 걸면 옛 ingest_run_id 파티션부터 사라져 재집계와 백필이
# 조용히 빈 구간을 만든다. verify.sh 가 curated 에 규칙이 없는지 확인한다.
cat > "$WORK/lifecycle.json" <<JSON
{
  "Rules": [
    {
      "ID": "expire-all",
      "Status": "Enabled",
      "Filter": { "Prefix": "" },
      "Expiration": { "Days": $MINIO_RAW_EXPIRE_DAYS }
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
echo "minio-init: buckets=$MINIO_BUCKET,$MINIO_CURATED_BUCKET crawler=$MINIO_CRAWLER_ACCESS_KEY($MINIO_BUCKET write) spark=$MINIO_SPARK_ACCESS_KEY($MINIO_BUCKET read, $MINIO_CURATED_BUCKET write)"
echo "minio-init: versioning=off lifecycle=$MINIO_BUCKET 전체 ${MINIO_RAW_EXPIRE_DAYS}일, $MINIO_CURATED_BUCKET 없음"
