#!/usr/bin/env bash
#
# 모든 엔드포인트를 같은 조건으로 재서 표 하나로 남긴다. 개선 전후를 나란히
# 놓는 것이 목적이므로, 조건을 하나라도 바꾸면 비교가 무의미해진다.
#
#   ./bench.sh baseline          현재 상태
#   ./bench.sh no-sql-logging    Hibernate SQL 로깅을 끈 뒤
#   ./bench.sh indexed           인덱스를 넣은 뒤
#
#   ./compare.sh baseline indexed
#
# 고정하는 것:
#
#   도착률   내내 10 RPS (CONSTANT_RATE). 램프를 쓰지 않는다. 램프를 섞으면
#            p95 에 낮은 부하 구간이 함께 들어가 회차마다 값이 흔들린다.
#            무릎 한참 아래라서 큐 대기가 섞이지 않고 서버 처리 시간만 남는다.
#   길이     본 측정 1분
#   워밍업   측정 전 20초. 버퍼 풀과 JIT 를 데운다. 이것이 없으면 나중에 잰
#            쪽이 그냥 두 번째라서 빨라, 개선한 것처럼 보인다.
#   데이터   재시딩 금지. 같은 데이터여야 한다.
#
set -euo pipefail

cd "$(dirname "$0")"

label=${1:-}
if [ -z "$label" ]; then
    echo '사용법: ./bench.sh <라벨>    예: ./bench.sh baseline' >&2
    exit 1
fi

BASE_URL=${BASE_URL:-http://127.0.0.1:18080}
BENCH_RATE=${BENCH_RATE:-10}
BENCH_DURATION=${BENCH_DURATION:-1m}
WARMUP_RATE=${WARMUP_RATE:-5}
WARMUP_DURATION=${WARMUP_DURATION:-20s}
RESULTS=results

SCRIPTS=(
    endpoint/trends-list.js
    endpoint/trend-contents.js
    endpoint/notifications.js
    endpoint/saved-trends.js
    endpoint/trend-history.js
    endpoint/trend-regions.js
    endpoint/auth-login.js
)

command -v k6 >/dev/null || { echo 'k6 가 설치돼 있지 않다.' >&2; exit 1; }

status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "${BASE_URL}/actuator/health" 2>/dev/null || echo 000)
if [ "$status" != "200" ]; then
    echo "대상이 응답하지 않는다 (${BASE_URL}, HTTP ${status}). 먼저 ../up.sh 를 돌린다." >&2
    exit 1
fi

mkdir -p "$RESULTS"
tsv="$RESULTS/bench-${label}.tsv"
: > "$tsv"

echo "라벨: $label   도착률: ${BENCH_RATE} RPS   길이: ${BENCH_DURATION}"
echo

for script in "${SCRIPTS[@]}"; do
    name=$(basename "$script" .js)
    raw="$RESULTS/bench-${label}-${name}.txt"

    printf '%-22s 워밍업... ' "$name"
    CONSTANT_RATE="$WARMUP_RATE" BENCH_DURATION="$WARMUP_DURATION" BASE_URL="$BASE_URL" \
        k6 run "$script" >/dev/null 2>&1 || true
    sleep 5

    printf '측정... '
    set +e
    CONSTANT_RATE="$BENCH_RATE" BENCH_DURATION="$BENCH_DURATION" BASE_URL="$BASE_URL" \
        k6 run "$script" > "$raw" 2>&1
    code=$?
    set -e

    if [ "$code" -ne 0 ] && [ "$code" -ne 99 ]; then
        echo "실패 (exit $code)"
        tail -3 "$raw" >&2
        continue
    fi

    # 태그별 줄에서 엔드포인트마다 한 행을 뽑는다. 스크립트 하나가 여러
    # 엔드포인트를 치므로, 스크립트 단위로 묶으면 어느 쪽이 느린지 가려진다.
    sed 's/µs/us/g' "$raw" | awk -v script="$name" -v label="$label" '
        function to_ms(v,   t, total, num, unit, rest) {
            total = 0; rest = v
            while (match(rest, /^[0-9.]+(us|ms|s|m|h)/)) {
                t = substr(rest, RSTART, RLENGTH)
                rest = substr(rest, RSTART + RLENGTH)
                if (t ~ /us$/)      { num = substr(t, 1, length(t) - 2) + 0; total += num / 1000 }
                else if (t ~ /ms$/) { num = substr(t, 1, length(t) - 2) + 0; total += num }
                else {
                    unit = substr(t, length(t), 1)
                    num = substr(t, 1, length(t) - 1) + 0
                    if (unit == "s")      total += num * 1000
                    else if (unit == "m") total += num * 60000
                    else if (unit == "h") total += num * 3600000
                }
            }
            return total
        }
        /name:/ && /avg=/ {
            if (!match($0, /name:[^}]+/)) next
            ep = substr($0, RSTART + 5, RLENGTH - 5)
            sub(/[ \t]+$/, "", ep)
            if (ep == "setup:login") next
            avg = med = p95 = ""
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^avg=/)      avg = substr($i, 5)
                if ($i ~ /^med=/)      med = substr($i, 5)
                if ($i ~ /^p\(95\)=/)  p95 = substr($i, 7)
            }
            printf "%s\t%s\t%s\t%.2f\t%.2f\t%.2f\n", label, script, ep, to_ms(avg), to_ms(med), to_ms(p95)
        }
    ' >> "$tsv"

    # ⚠️ `\.*:` 가 있어야 한다. k6 는 `http_req_failed` 를 **두 번** 찍는다 — 임계값
    # 목록(`█ THRESHOLDS`)에 이름만 한 줄, 그리고 `█ TOTAL RESULTS` 에 값이 붙은 줄.
    # 앞의 것이 파일에서 먼저 나오므로 `-m1` 이 값 없는 줄을 잡고, 뒤의 `%` 추출이
    # 빈손으로 끝난다. 그 실패가 `set -e` 에 걸려 **첫 스크립트에서 스크립트 전체가
    # 죽었다** — 표에 한 줄만 남고 2번째 raw 파일은 만들어지지도 않았다. 점과 콜론은
    # 값이 붙은 줄에만 있다.
    #
    # `|| true` 는 그 다음 방어다. 이 값은 진행 표시용이라, 못 뽑았다고 측정을
    # 멈출 이유가 없다. `${fail:-?}` 기본값이 쓰일 기회를 `set -e` 가 빼앗지 않게 한다.
    fail=$(grep -m1 -E '^[[:space:]]+http_req_failed\.*:' "$raw" \
        | grep -oE '[0-9.]+%' | head -1 || true)
    echo "완료 (실패 ${fail:-?})"
done

echo
printf '%-26s %-46s %10s %10s %10s\n' '스크립트' '엔드포인트' 'avg(ms)' 'med(ms)' 'p95(ms)'
printf '%s\n' '--------------------------------------------------------------------------------------------------------'
awk -F'\t' '{ printf "%-26s %-46s %10.1f %10.1f %10.1f\n", $2, $3, $4, $5, $6 }' "$tsv"

echo
echo "표: $tsv"
echo "전후 비교: ./compare.sh <이전라벨> ${label}"
