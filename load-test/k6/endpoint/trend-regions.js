// 지역 관련 세 엔드포인트. keyword_country_daily_metrics 242만 행을 읽는다.
//
// journey 를 특히 본다. 나라별 첫 등장일을 구하려고 group by country_code 에
// min(metric_date) 를 건다. 유니크 제약이 (keyword_id, metric_date, country_code)
// 순서라 keyword_id 로 좁히는 것까지는 인덱스가 돕지만, 그 안에서 나라별로 묶는
// 일은 남는다. 한 키워드에 20개국 × 최대 90일이 들어 있다.

import { check } from 'k6';
import { BASE_URL, hotTrendId, lightMemberId, arrivalRate, baseThresholds } from '../lib/config.js';
import { tokensFor, pickToken, authGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 20);
const TOKEN_POOL = Number(__ENV.TOKEN_POOL || 50);

const REGIONS = 'GET /trends/{id}/regions';
const REGION_HISTORY = 'GET /trends/{id}/regions/{code}/history';
const JOURNEY = 'GET /trends/{id}/regions/journey';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${REGIONS}}`]: ['p(95)<1000'],
    [`http_req_duration{name:${REGION_HISTORY}}`]: ['p(95)<1000'],
    [`http_req_duration{name:${JOURNEY}}`]: ['p(95)<1500'],
  },
};

export function setup() {
  return { tokens: tokensFor(lightMemberId, TOKEN_POOL) };
}

export default function (data) {
  const token = pickToken(data.tokens);
  // 국가 데이터는 상위 2,000 개 키워드에만 넣었다. 그 밖을 고르면 빈 결과가 와서
  // 아무것도 재지 못한다.
  const id = hotTrendId(__ITER * 11 + __VU);

  check(authGet(`${BASE_URL}/trends/${id}/regions?period=30D`, token, REGIONS), {
    '지역 목록 200': (r) => r.status === 200,
  });

  check(
    authGet(`${BASE_URL}/trends/${id}/regions/KR/history?period=30D`, token, REGION_HISTORY),
    { '지역 이력 200': (r) => r.status === 200 },
  );

  check(authGet(`${BASE_URL}/trends/${id}/regions/journey`, token, JOURNEY), {
    'journey 200': (r) => r.status === 200,
  });
}
