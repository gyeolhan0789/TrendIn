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

echo
echo '기동을 기다리는 중...'
port=${LOADTEST_BACKEND_PORT:-18080}
attempt=1
while [ "$attempt" -le 60 ]; do
    if status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
        "http://127.0.0.1:${port}/actuator/health" 2>/dev/null); then
        if [ "$status" = "200" ]; then
            echo "떴다: http://127.0.0.1:${port}"
            exit 0
        fi
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo "120초 안에 뜨지 않았다. 로그를 본다:" >&2
echo "  docker compose -p s15p21a102-loadtest logs --tail=50 backend-loadtest" >&2
exit 1
