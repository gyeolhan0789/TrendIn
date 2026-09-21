#!/usr/bin/env bash
#
# 한 엔드포인트를 여러 도착률로 돌려 무릎(knee)을 찾는다.
#
#   ./sweep.sh endpoint/notifications.js             5 10 20 40 으로 훑는다
#   ./sweep.sh endpoint/notifications.js 2 5 10 20   직접 지정
#
# 한 번 재서 나온 p95 하나는 한계가 아니다. 도착률을 올려 가며 **응답시간이 꺾이고
# dropped_iterations 가 붙기 시작하는 지점**을 찾아야 그것이 그 엔드포인트의 한계다.
#
# 각 회차는 짧게 돈다(기본 15초 × 4 + 30초 = 1분 30초). 정확한 꼬리값보다 꺾이는
# 자리를 찾는 것이 목적이다. 자리를 찾은 뒤 그 값으로 run.sh 를 한 번 길게 돌린다.
#
set -euo pipefail

cd "$(dirname "$0")"

BASE_URL=${BASE_URL:-http://127.0.0.1:18080}
RESULTS=results

command -v k6 >/dev/null || { echo 'k6 가 설치돼 있지 않다.' >&2; exit 1; }

script=${1:-}
test -n "$script" || { echo '사용법: ./sweep.sh <스크립트> [rps ...]' >&2; exit 1; }
test -f "$script" || { echo "그런 파일이 없다: $script" >&2; exit 1; }
shift

if [ "$#" -gt 0 ]; then
    rates=("$@")
else
    rates=(5 10 20 40)
fi

status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "${BASE_URL}/actuator/health" 2>/dev/null || echo 000)
if [ "$status" != "200" ]; then
    echo "대상이 응답하지 않는다 (${BASE_URL}, HTTP ${status}). 먼저 ../up.sh 를 돌린다." >&2
    exit 1
fi

mkdir -p "$RESULTS"
name=$(basename "$script" .js)
stamp=$(date +%Y%m%d-%H%M%S)
table="$RESULTS/${name}-sweep-${stamp}.txt"

# 회차마다 값을 뽑아 표로 쌓는다. k6 요약은 사람이 읽기 좋지만 회차 비교에는 불편하다.
extract() {
    local file=$1 field=$2
    case "$field" in
        p95)   grep -m1 -oE 'p\(95\)=[^ ]+' "$file" | cut -d= -f2 ;;
        rps)   grep -m1 -E '^[[:space:]]+http_reqs' "$file" | grep -oE '[0-9.]+/s' | head -1 ;;
        fail)  grep -m1 -E '^[[:space:]]+http_req_failed' "$file" | grep -oE '[0-9.]+%' | head -1 ;;
        drop)  grep -m1 -E '^[[:space:]]+dropped_iterations' "$file" | awk '{print $2}' ;;
    esac
}

{
    echo "스크립트: $script"
    echo "시각:     $stamp"
    echo
    printf '%-10s %-12s %-12s %-10s %-10s\n' '목표RPS' '달성RPS' 'p95' '실패율' '드롭'
    printf '%s\n' '------------------------------------------------------------'
} | tee "$table"

for rps in "${rates[@]}"; do
    out="$RESULTS/${name}-rps${rps}-${stamp}.txt"
    echo
    echo "--- PEAK_RPS=$rps ---"

    set +e
    PEAK_RPS="$rps" \
    STAGE_DURATION="${STAGE_DURATION:-15s}" \
    HOLD_DURATION="${HOLD_DURATION:-30s}" \
    BASE_URL="$BASE_URL" \
        k6 run "$script" > "$out" 2>&1
    code=$?
    set -e

    if [ "$code" -ne 0 ] && [ "$code" -ne 99 ]; then
        echo "실행 실패 (exit $code). $out 를 본다." >&2
        tail -5 "$out" >&2
        continue
    fi

    got=$(extract "$out" rps)
    p95=$(extract "$out" p95)
    fail=$(extract "$out" fail)
    drop=$(extract "$out" drop)
    row=$(printf '%-10s %-12s %-12s %-10s %-10s' \
        "$rps" "${got:-?}" "${p95:-?}" "${fail:-?}" "${drop:-0}")
    echo "$row"
    echo "$row" >> "$table"

    # 앞 회차의 GC 와 커넥션 정리가 다음 회차에 섞이지 않게 쉰다.
    sleep 15
done

echo
echo '=============================================================='
cat "$table"
echo '=============================================================='
echo
echo "달성RPS 가 목표를 못 따라가기 시작하거나 드롭이 붙는 첫 지점이 무릎이다."
echo "표: $table"
