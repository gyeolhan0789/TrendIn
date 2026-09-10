#!/usr/bin/env sh
# datastore/compose.yaml 의 값 다섯 개는 배포되면 되돌릴 수 없다. target 브랜치와 비교해
# 위험한 방향으로 바뀌었으면 실패한다.
# 일부러 바꾼 것이면 커밋 메시지에 `Allow-destructive: <키>` 한 줄을 넣어 통과시킨다.
#
# 값은 `docker compose config` 가 푼 결과에서 읽는다. 파일을 정규식으로 긁으면
# `KEY: 1` 이나 `KEY: "${VAR:-1}"` 처럼 꼴만 바뀐 것을 못 읽는데, 못 읽은 것을 넘어가면
# 가드가 조용히 뚫린다. 읽지 못하는 모든 경우는 통과가 아니라 실패다.
#
# 서버의 .env 로 값을 덮으면 Git 에 안 남아 여기서 못 잡는다.
set -eu

TARGET=${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-dev}
WORK=$(mktemp -d)
FAIL=0

git fetch -q origin "$TARGET"
git archive "origin/$TARGET" datastore | tar x -C "$WORK"
if [ ! -f "$WORK/datastore/compose.yaml" ]; then
  echo "origin/$TARGET 에 datastore/compose.yaml 이 없다 — 건너뛴다"
  exit 0
fi

ALLOWED=$(git log --format=%B "origin/$TARGET..HEAD" | sed -n 's/^Allow-destructive: *//p' | tr '\n' ' ')

# compose 를 풀어 JSON 으로 뽑는다. `${VAR:?}` 로 요구되는 비밀값은 이름을 파일에서
# 뽑아 더미로 채운다 — datastore:compose 잡과 같은 방식이다.
#
# `--env-file /dev/null` 로 .env 자동 로딩을 끈다. 기준 쪽은 git 에서 꺼내 .env 가
# 없는데 비교 대상 쪽에만 있으면, 같은 파일을 서로 다른 값으로 재게 된다.
resolve() {
  (
    cd "$1"
    for n in $(grep -o '\${[A-Z_][A-Z_0-9]*:?' compose.yaml | sed 's/^\${//; s/:?$//' | sort -u); do
      export "$n=ci-dummy"
    done
    docker compose --env-file /dev/null -f compose.yaml config --format json
  )
}
resolve "$WORK/datastore" > "$WORK/base.json"
resolve datastore         > "$WORK/head.json"

# 어느 서비스에 붙어 있든 그 이름의 환경변수를 찾는다.
val() {
  jq -r --arg k "$1" '[.services[].environment[$k]? | select(. != null)] | first // ""' "$2"
}

report() {
  case " $ALLOWED " in
    *" $1 "*) echo "  허용  $1 — 커밋 메시지에 Allow-destructive 가 있다" ;;
    *)        echo "  거부  $1 — $2"; FAIL=1 ;;
  esac
}

# 없어진 것도 위험하다. 설정이 빠지면 브로커나 버킷 기본값으로 돌아간다.
# 양쪽 다 없으면 비교할 것이 없다.
present() {
  if [ -z "$1" ] && [ -z "$2" ]; then return 1; fi
  if [ -z "$1" ]; then echo "  ok    $3  새로 생김 → $2"; return 1; fi
  if [ -z "$2" ]; then report "$3" "$1 이었는데 없어졌다. 기본값으로 돌아간다"; return 1; fi
  return 0
}

# $1 키  $2 위험한 방향(down|up)  $3 되돌리면 어떻게 되는지
check_num() {
  old=$(val "$1" "$WORK/base.json")
  new=$(val "$1" "$WORK/head.json")
  present "$old" "$new" "$1" || return 0
  if [ "$old" = "$new" ]; then return 0; fi
  # 숫자로 안 읽히면 방향을 판단할 수 없다. 넘어가지 않고 사람에게 넘긴다.
  case "$old$new" in
    *[!0-9]*) report "$1" "숫자로 읽히지 않는다 ($old → $new). 사람이 본다"; return 0 ;;
  esac
  if [ "$2" = down ] && [ "$new" -lt "$old" ]; then
    report "$1" "$old → $new 로 줄었다. $3"
  elif [ "$2" = up ] && [ "$new" -gt "$old" ]; then
    report "$1" "$old → $new 로 늘었다. $3"
  else
    echo "  ok    $1  $old → $new"
  fi
}

echo "되돌릴 수 없는 설정 검사 — 기준 origin/$TARGET"
check_num KAFKA_LOG_RETENTION_HOURS down "이미 지워진 메시지는 안 돌아온다"
check_num KAFKA_TOPIC_RETENTION_MS  down "이미 지워진 메시지는 안 돌아온다"
check_num MINIO_RAW_EXPIRE_DAYS     down "이미 만료된 원문은 안 돌아온다"
check_num KAFKA_TOPIC_PARTITIONS    up   "파티션은 줄이지 못한다. 토픽을 지워야 한다"

old=$(val KAFKA_TOPIC_CLEANUP_POLICY "$WORK/base.json")
new=$(val KAFKA_TOPIC_CLEANUP_POLICY "$WORK/head.json")
if present "$old" "$new" KAFKA_TOPIC_CLEANUP_POLICY && [ "$old" != "$new" ]; then
  if [ "$new" = compact ]; then
    report KAFKA_TOPIC_CLEANUP_POLICY "$old → compact. 같은 키의 옛 메시지가 정리된 뒤다"
  else
    echo "  ok    KAFKA_TOPIC_CLEANUP_POLICY  $old → $new"
  fi
fi

if [ "$FAIL" = 1 ]; then
  echo
  echo "의도한 변경이면 커밋 메시지에 다음 줄을 넣는다 — MR 에 그대로 보여 리뷰가 알아본다."
  echo "  Allow-destructive: <키>"
  exit 1
fi
echo "통과"
