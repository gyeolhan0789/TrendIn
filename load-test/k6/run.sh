#!/usr/bin/env bash
#
# 엔드포인트별 측정을 순서대로 돌리고 결과를 results/ 에 남긴다.
#
#   ./run.sh                          전부
#   ./run.sh endpoint/notifications.js  하나만
#   PEAK_RPS=300 ./run.sh endpoint/notifications.js
#
# 한계를 찾는 방법은 PEAK_RPS 를 올려 가며 다시 돌리는 것이다. 응답시간이 꺾이고
# 에러가 붙기 시작하는 지점이 그 엔드포인트의 한계다.
#
# Prometheus 로 결과를 밀어넣으려면 (Grafana 에서 서버 지표와 겹쳐 본다):
#   export K6_PROMETHEUS_RW_SERVER_URL=http://localhost:9090/api/v1/write
#   export K6_OUT=experimental-prometheus-rw      # k6 버전에 따라 이름이 다르다
#
set -euo pipefail

cd "$(dirname "$0")"

BASE_URL=${BASE_URL:-http://127.0.0.1:18080}
RESULTS=results

command -v k6 >/dev/null || { echo 'k6 가 설치돼 있지 않다.' >&2; exit 1; }

# 대상이 떠 있지 않으면 전부 연결 실패로 끝난다. 3분을 버리기 전에 막는다.
status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "${BASE_URL}/actuator/health" 2>/dev/null || echo 000)
if [ "$status" != "200" ]; then
    echo "부하테스트 대상이 응답하지 않는다 (${BASE_URL}, HTTP ${status})." >&2
    echo '먼저 ../up.sh 로 스택을 올린다.' >&2
    exit 1
fi

if [ "$#" -gt 0 ]; then
    # 오타로 없는 파일을 주면 k6 가 3분짜리 자리를 잡아 놓고 실패한다.
    for s in "$@"; do
        test -f "$s" || { echo "그런 파일이 없다: $s" >&2; exit 1; }
    done
    scripts=("$@")
else
    # 가벼운 것부터. 앞에서 터지면 뒤는 볼 필요가 없다.
    scripts=(
        endpoint/trends-list.js
        endpoint/trend-contents.js
        endpoint/notifications.js
        endpoint/saved-trends.js
        endpoint/trend-history.js
        endpoint/trend-regions.js
        endpoint/auth-login.js
    )
fi

mkdir -p "$RESULTS"
stamp=$(date +%Y%m%d-%H%M%S)

for script in "${scripts[@]}"; do
    name=$(basename "$script" .js)
    out="$RESULTS/${name}-${stamp}.txt"

    echo
    echo "=============================================================="
    echo " $script   (PEAK_RPS=${PEAK_RPS:-스크립트 기본값})"
    echo "=============================================================="

    # 임계값을 넘겨도 다음 스크립트로 넘어간다. 한계를 찾는 것이 목적이라
    # 넘기는 것 자체가 결과다. k6 는 그 경우 99 로 끝난다.
    set +e
    BASE_URL="$BASE_URL" k6 run "$script" 2>&1 | tee "$out"
    code=${PIPESTATUS[0]}
    set -e

    case "$code" in
        0)  echo "→ 임계값 통과. $out" ;;
        99) echo "→ 임계값 초과(측정은 정상). $out" ;;
        *)  echo "→ 실행 실패 (exit $code). $out" >&2 ;;
    esac

    # 다음 측정이 앞 측정의 GC 와 커넥션 정리에 물리지 않게 잠깐 쉰다.
    sleep 10
done

echo
echo "결과: $RESULTS/*-${stamp}.txt"
