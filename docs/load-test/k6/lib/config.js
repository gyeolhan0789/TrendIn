// 스크립트들이 함께 쓰는 값과 도우미.

export const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:18080';

// docs/load-test/seed/06_members.sql 이 만든 계정이다. 한쪽만 바꾸면 로그인이 전부 실패한다.
export const PASSWORD = __ENV.LOADTEST_PASSWORD || 'Loadtest1234!';

export const MEMBER_COUNT = Number(__ENV.MEMBER_COUNT || 10000);
export const KEYWORD_COUNT = Number(__ENV.KEYWORD_COUNT || 50000);

// 시드가 상위 2,000 개 키워드에 콘텐츠와 국가 데이터를 몰아줬다. 트렌드는 키워드와
// 1:1 이라 id 가 같다. 이 범위를 골라야 실제로 사람들이 보는 화면을 재게 된다.
export const HOT_TREND_COUNT = Number(__ENV.HOT_TREND_COUNT || 2000);

// 한 요청이 이만큼을 넘기면 그 시점의 서버는 이미 쓸 수 없는 상태다. 기다려 봐야
// 큐 대기 시간만 재게 되고, k6 기본값 60초로 두면 붕괴한 측정이 몇 분을 더 끈다.
export const REQUEST_TIMEOUT = __ENV.REQUEST_TIMEOUT || '15s';

const BLOCKS = MEMBER_COUNT / 100;

// 시드는 회원을 id % 100 으로 갈랐다(07_activity.sql).
//   0~49 아무것도 없음 · 50~79 가벼움 · 80~94 보통 · 95~99 헤비
//
// 헤비 회원이 최악의 경우다. verify.sql 이 뽑아 준 id 를 그대로 박아 두면 시드
// 규모를 바꿀 때 조용히 어긋나므로, 규칙에서 계산한다.
export function heavyMemberId(n) {
  return (Math.floor(n / 5) % BLOCKS) * 100 + 95 + (n % 5);
}

// 비교용. 평균적인 사용자는 같은 조회가 얼마나 걸리는지 본다.
export function lightMemberId(n) {
  return (Math.floor(n / 30) % BLOCKS) * 100 + 50 + (n % 30);
}

export function hotTrendId(n) {
  return 1 + (n % HOT_TREND_COUNT);
}

export function anyTrendId(n) {
  return 1 + (n % KEYWORD_COUNT);
}

// 고정 VU 로 재면 서버가 느려질 때 요청도 같이 느려진다. 부하가 저절로 줄어드니
// 포화점이 보이지 않고, 그래프는 완만하게 눕는다. 도착률을 고정해 올려야 서버가
// 감당 못 하는 지점에서 큐가 쌓이고 응답시간이 꺾인다.
//
// maxVUs 를 크게 잡으면 안 된다. 서버가 느려질수록 VU 가 쌓이는데, k6 는 같은
// EC2 에서 돌고 코어는 몇 개 없다. VU 수백 개가 뜨는 순간 k6 가 서버의 CPU 를
// 뺏어, 무엇이 한계였는지 구분할 수 없게 된다. 목표 도착률을 못 채우면(=
// dropped_iterations 가 쌓이면) 그것은 이미 서버가 감당하지 못한다는 신호이므로,
// VU 를 더 부어 억지로 채울 이유가 없다.
export function arrivalRate(peakRps, opts = {}) {
  const maxVUs = Number(__ENV.MAX_VUS || opts.maxVUs || 200);

  // 기준 측정(bench.sh)은 램프를 쓰지 않는다. 램프를 섞으면 p95 에 낮은 부하
  // 구간이 함께 들어가, 같은 값으로 다시 재도 구간 비율이 조금만 달라지면
  // 숫자가 흔들린다. 개선 전후를 나란히 놓으려면 내내 같은 도착률이어야 한다.
  if (__ENV.CONSTANT_RATE) {
    const rate = Number(__ENV.CONSTANT_RATE);
    return {
      executor: 'constant-arrival-rate',
      rate,
      timeUnit: '1s',
      duration: __ENV.BENCH_DURATION || '1m',
      preAllocatedVUs: Math.min(50, maxVUs),
      maxVUs,
    };
  }

  // 무릎을 찾을 때는 램프로 올린다.
  const stage = __ENV.STAGE_DURATION || '30s';
  const hold = __ENV.HOLD_DURATION || '1m';
  return {
    executor: 'ramping-arrival-rate',
    startRate: Math.max(1, Math.round(peakRps / 10)),
    timeUnit: '1s',
    preAllocatedVUs: Math.min(50, maxVUs),
    maxVUs,
    stages: [
      { target: Math.round(peakRps * 0.25), duration: stage },
      { target: Math.round(peakRps * 0.5), duration: stage },
      { target: Math.round(peakRps * 0.75), duration: stage },
      { target: peakRps, duration: stage },
      { target: peakRps, duration: hold },
    ],
  };
}

// 한계를 찾는 것이 목적이라 임계값을 넘겨도 중단하지 않는다. 넘긴 사실만 남긴다.
export const baseThresholds = {
  http_req_failed: ['rate<0.01'],
};
