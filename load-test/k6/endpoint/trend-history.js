// 트렌드 시계열. keyword_metric_history 450만 행 위를 긁는다.
//
// (keyword_id, bucket_start) 유니크 인덱스가 있으므로 범위 조회는 인덱스를 탈
// 것으로 본다. 확인하려는 것은 기간에 따라 비용이 어떻게 늘어나는지다. 30D 는
// 24H 보다 30배 많은 행을 읽는다. 선형으로 늘면 정상이고, 그보다 가파르면
// 인덱스를 못 타고 있다는 뜻이다.

import { check } from 'k6';
import { BASE_URL, hotTrendId, lightMemberId, arrivalRate, baseThresholds } from '../lib/config.js';
import { tokensFor, pickToken, authGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 100);
const TOKEN_POOL = Number(__ENV.TOKEN_POOL || 50);

const DETAIL = 'GET /trends/{id}';
const H24 = 'GET /trends/{id}/history?period=24H';
const H30 = 'GET /trends/{id}/history?period=30D';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${DETAIL}}`]: ['p(95)<500'],
    [`http_req_duration{name:${H24}}`]: ['p(95)<500'],
    [`http_req_duration{name:${H30}}`]: ['p(95)<1000'],
  },
};

export function setup() {
  // 상세 조회는 인증이 필요하다. 개인화가 없으므로 평범한 회원으로 충분하다.
  return { tokens: tokensFor(lightMemberId, TOKEN_POOL) };
}

export default function (data) {
  const token = pickToken(data.tokens);
  // 콘텐츠와 지표가 몰려 있는 상위 트렌드를 고른다.
  const id = hotTrendId(__ITER * 7 + __VU);

  check(authGet(`${BASE_URL}/trends/${id}?period=7D`, token, DETAIL), {
    '상세 200': (r) => r.status === 200,
  });

  check(authGet(`${BASE_URL}/trends/${id}/history?period=24H`, token, H24), {
    '24H 이력 200': (r) => r.status === 200,
  });

  check(authGet(`${BASE_URL}/trends/${id}/history?period=30D`, token, H30), {
    '30D 이력 200': (r) => r.status === 200,
  });
}
