// 저장한 트렌드 목록.
//
// saved_trends 는 UNIQUE (member_id, trend_id) 를 갖고 있어 member_id 로 시작하는
// 인덱스가 있다. 그래서 알림과 달리 조회 자체는 인덱스를 탄다. 비교군으로 둔다.
//
// 대신 이 API 는 목록을 만들며 트렌드와 분석을 함께 읽는다. 헤비 회원은 저장이
// 100~500건이라, 인덱스가 있어도 뒤따르는 조인이 비싸다면 거기서 드러난다.

import { check } from 'k6';
import { BASE_URL, heavyMemberId, arrivalRate, baseThresholds } from '../lib/config.js';
import { tokensFor, pickToken, authGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 100);
const TOKEN_POOL = Number(__ENV.TOKEN_POOL || 50);

const SAVED = 'GET /members/me/saved-trends';
const INTEREST = 'GET /members/me/interest-keywords';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${SAVED}}`]: ['p(95)<1000'],
    [`http_req_duration{name:${INTEREST}}`]: ['p(95)<500'],
  },
};

export function setup() {
  return { tokens: tokensFor(heavyMemberId, TOKEN_POOL) };
}

export default function (data) {
  const token = pickToken(data.tokens);

  const saved = authGet(
    `${BASE_URL}/members/me/saved-trends?period=7D&page=0&size=20`,
    token,
    SAVED,
  );
  check(saved, { '저장한 트렌드 200': (r) => r.status === 200 });

  const interest = authGet(`${BASE_URL}/members/me/interest-keywords`, token, INTEREST);
  check(interest, { '관심 키워드 200': (r) => r.status === 200 });
}
