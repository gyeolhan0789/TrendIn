// 스크립트들이 함께 쓰는 값과 도우미.

export const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:18080';

// load-test/seed/06_members.sql 이 만든 계정이다. 한쪽만 바꾸면 로그인이 전부 실패한다.
export const PASSWORD = __ENV.LOADTEST_PASSWORD || 'Loadtest1234!';

export const MEMBER_COUNT = Number(__ENV.MEMBER_COUNT || 10000);
export const KEYWORD_COUNT = Number(__ENV.KEYWORD_COUNT || 50000);

// 시드가 상위 2,000 개 키워드에 콘텐츠와 국가 데이터를 몰아줬다. 트렌드는 키워드와
// 1:1 이라 id 가 같다. 이 범위를 골라야 실제로 사람들이 보는 화면을 재게 된다.
export const HOT_TREND_COUNT = Number(__ENV.HOT_TREND_COUNT || 2000);

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
export function arrivalRate(peakRps) {
  return {
    executor: 'ramping-arrival-rate',
    startRate: Math.max(1, Math.round(peakRps / 10)),
    timeUnit: '1s',
    // 서버가 느려지면 한 요청이 VU 를 오래 붙잡는다. 넉넉히 잡아 두지 않으면
    // k6 가 VU 부족으로 목표 도착률을 못 채우고, 그것이 서버 한계처럼 보인다.
    preAllocatedVUs: 50,
    maxVUs: 1000,
    stages: [
      { target: Math.round(peakRps * 0.25), duration: '30s' },
      { target: Math.round(peakRps * 0.5), duration: '30s' },
      { target: Math.round(peakRps * 0.75), duration: '30s' },
      { target: peakRps, duration: '30s' },
      { target: peakRps, duration: '1m' },
    ],
  };
}

// 한계를 찾는 것이 목적이라 임계값을 넘겨도 중단하지 않는다. 넘긴 사실만 남긴다.
export const baseThresholds = {
  http_req_failed: ['rate<0.01'],
};
