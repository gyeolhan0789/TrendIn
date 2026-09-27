#!/usr/bin/env bash
#
# bench.sh 가 만든 표 둘을 나란히 놓고 개선율을 계산한다.
#
#   ./compare.sh baseline indexed
#
# 두 측정이 같은 조건이었을 때만 의미가 있다. 사이에 재시딩을 했거나
# BENCH_RATE 를 바꿨다면 비교하지 않는다.
#
set -euo pipefail

cd "$(dirname "$0")"

before=${1:-}
after=${2:-}
if [ -z "$before" ] || [ -z "$after" ]; then
    echo '사용법: ./compare.sh <이전라벨> <이후라벨>' >&2
    exit 1
fi

b="results/bench-${before}.tsv"
a="results/bench-${after}.tsv"
test -f "$b" || { echo "그런 표가 없다: $b" >&2; exit 1; }
test -f "$a" || { echo "그런 표가 없다: $a" >&2; exit 1; }

echo "$before  →  $after"
echo
printf '%-46s %12s %12s %10s\n' '엔드포인트' "p95 (${before})" "p95 (${after})" '변화'
printf '%s\n' '-------------------------------------------------------------------------------------------'

awk -F'\t' -v bf="$b" '
    BEGIN {
        while ((getline line < bf) > 0) {
            split(line, f, "\t")
            key = f[3]
            before_p95[key] = f[6]
            order[++n] = key
        }
    }
    { after_p95[$3] = $6 }
    END {
        for (i = 1; i <= n; i++) {
            key = order[i]
            bv = before_p95[key]
            if (!(key in after_p95)) {
                printf "%-46s %12.1f %12s %10s\n", key, bv, "-", "없음"
                continue
            }
            av = after_p95[key]
            if (bv > 0) {
                delta = (av - bv) / bv * 100
                # 빨라지면 음수다. 사람이 읽기 쉽게 부호를 뒤집어 개선율로 보인다.
                printf "%-46s %12.1f %12.1f %9.1f%%\n", key, bv, av, -delta
            } else {
                printf "%-46s %12.1f %12.1f %10s\n", key, bv, av, "-"
            }
        }
    }
' "$a"

echo
echo '변화 열은 개선율이다. 양수면 빨라진 것, 음수면 느려진 것.'
