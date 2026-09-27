#!/usr/bin/env bash
#
# trendin_test 에 부하테스트용 더미 데이터를 붓는다.
#
#   ./seed.sh            순서대로 전부 실행한다
#   ./seed.sh --verify   확인 질의만 다시 돌린다
#   ./seed.sh --reset    시드를 비운다 (TRUNCATE. 되돌릴 수 없다)
#
# 운영과 같은 PostgreSQL 인스턴스다. 수백만 행이 들어가는 동안 버퍼 풀이 밀리고
# 디스크가 바빠져 운영 응답이 느려진다. 발표·데모·팀원 QA 가 없는 시간에 돌린다.
#
# 전체 20~40분을 예상한다. 03(일별 이력 450만)과 04(국가별 240만)가 대부분이다.
#
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE=../../infra/.env
INFRA_COMPOSE=../../infra/compose.yaml
DB=trendin_test

test -r "$ENV_FILE" || { echo "infra/.env 를 읽을 수 없다: $ENV_FILE" >&2; exit 1; }

psql_file() {
    # 서버 안에서 generate_series 가 행을 만든다. 파일만 표준입력으로 넘어가고
    # 데이터가 네트워크를 타지 않는다.
    docker compose --env-file "$ENV_FILE" -f "$INFRA_COMPOSE" exec -T postgres \
        psql -U ssafy -d "$DB" -v ON_ERROR_STOP=1 --quiet < "$1"
}

run_step() {
    local file=$1
    local started elapsed
    printf '%-32s ' "$(basename "$file")"
    started=$(date +%s)
    if ! psql_file "$file"; then
        echo >&2
        echo "실패: $file" >&2
        echo '이미 들어간 행은 남아 있다. 다시 부으려면 ./seed.sh --reset 부터 한다.' >&2
        exit 1
    fi
    elapsed=$(( $(date +%s) - started ))
    printf '%ds\n' "$elapsed"
}

case "${1:-}" in
    --verify)
        psql_file seed/verify.sql
        exit 0
        ;;
    --reset)
        # 되돌릴 수 없는 작업이다. 데이터베이스 이름을 직접 치게 한다.
        printf '%s 의 시드 테이블을 모두 비운다. 계속하려면 데이터베이스 이름을 입력한다: ' "$DB"
        read -r answer
        if [ "$answer" != "$DB" ]; then
            echo '취소했다.'
            exit 1
        fi
        psql_file seed/reset.sql
        exit 0
        ;;
    '')
        ;;
    *)
        echo "알 수 없는 옵션: $1" >&2
        exit 1
        ;;
esac

echo "대상: $DB"
echo

run_step seed/00_guard.sql
run_step seed/01_keywords_trends.sql
run_step seed/02_contents.sql
run_step seed/03_metrics.sql
run_step seed/04_country_metrics.sql
run_step seed/05_relations.sql
run_step seed/06_members.sql
run_step seed/07_activity.sql
run_step seed/99_finalize.sql

echo
psql_file seed/verify.sql

echo
echo '시드 완료. 로그인 계정은 load1@test.com ~ load10000@test.com, 비밀번호는 Loadtest1234! 다.'
