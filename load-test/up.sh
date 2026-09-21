#!/usr/bin/env bash
#
# 부하테스트 스택을 올린다. 운영이 "지금 돌리고 있는" 이미지를 찾아 그대로 쓴다.
#
# infra/.env 의 BACKEND_IMAGE 를 그냥 읽으면 안 된다. CD 는 이미지 태그를 셸
# 환경변수로만 넘기고(`BACKEND_IMAGE="$RELEASE_IMAGE" docker compose up ...`)
# .env 에 써넣지 않는다. 그래서 .env 값은 최초 설정 그대로 멈춰 있고, 그걸
# 쓰면 몇 주 전 이미지를 재게 된다. 스키마는 운영에서 떠오는데 코드만 옛것이면
# Hibernate 가 없는 컬럼을 찾다가 기동에 실패한다.
#
#   ./up.sh              운영과 같은 이미지로 올린다
#   ./up.sh --recreate   컨테이너를 강제로 다시 만든다 (배포 후 재측정할 때)
#
set -euo pipefail

cd "$(dirname "$0")"

INFRA_DIR=../infra
ENV_FILE="$INFRA_DIR/.env"
INFRA_COMPOSE="$INFRA_DIR/compose.yaml"
LOADTEST_COMPOSE=compose.loadtest.yaml

test -r "$ENV_FILE" || {
    echo "infra/.env 를 읽을 수 없다: $ENV_FILE" >&2
    exit 1
}

prod_container=$(docker compose --env-file "$ENV_FILE" -f "$INFRA_COMPOSE" ps --quiet backend)
test -n "$prod_container" || {
    echo '운영 backend 컨테이너가 떠 있지 않다. 부하테스트는 그 이미지를 빌려 쓰므로' >&2
    echo 'infra/compose.yaml 을 먼저 올려야 한다.' >&2
    exit 1
}

prod_image=$(docker inspect --format '{{.Config.Image}}' "$prod_container")
echo "운영이 쓰는 이미지: $prod_image"

extra=()
if [ "${1:-}" = "--recreate" ]; then
    extra+=(--force-recreate)
fi

LOADTEST_BACKEND_IMAGE="$prod_image" docker compose \
    --env-file "$ENV_FILE" -f "$LOADTEST_COMPOSE" \
    up --detach "${extra[@]}"


port=${LOADTEST_BACKEND_PORT:-18080}
health="http://127.0.0.1:${port}/actuator/health"
project=s15p21a102-loadtest

echo
echo "기동을 기다린다: $health"

status=000
attempt=1
while [ "$attempt" -le 60 ]; do
    status=$(curl --silent --output /dev/null --write-out '%{http_code}' "$health" 2>/dev/null || echo 000)

    case "$status" in
        200)
            echo "떴다: http://127.0.0.1:${port}"
            exit 0
            ;;
        503)
            # 애플리케이션은 떴는데 DB 나 Redis 가 DOWN 이다. 기다려도 낫지 않는
            # 종류라, 어느 쪽인지 보여주고 바로 끝낸다.
            echo "애플리케이션은 떴지만 health 가 DOWN 이다 (HTTP 503)." >&2
            echo >&2
            curl --silent "$health" >&2 || true
            echo >&2
            exit 1
            ;;
    esac

    # 컨테이너가 죽었으면 60번을 다 세는 것은 시간 낭비다.
    if ! docker compose -p "$project" ps --status running --quiet backend-loadtest | grep -q .; then
        echo "backend-loadtest 컨테이너가 떠 있지 않다. 마지막 로그:" >&2
        echo >&2
        docker compose -p "$project" logs --tail=40 --no-color backend-loadtest >&2 || true
        exit 1
    fi

    # 10초마다 한 번씩만 알린다. 아무것도 안 나오면 멈춘 것처럼 보인다.
    if [ $((attempt % 5)) = 0 ]; then
        echo "  ... ${attempt}/60 (마지막 응답 ${status})"
    fi

    attempt=$((attempt + 1))
    sleep 2
done

echo "120초 안에 뜨지 않았다 (마지막 응답 ${status}). 마지막 로그:" >&2
echo >&2
docker compose -p "$project" logs --tail=40 --no-color backend-loadtest >&2 || true
exit 1
