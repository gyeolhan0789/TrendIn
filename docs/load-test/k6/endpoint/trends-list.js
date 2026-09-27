// 랜딩의 트렌드 목록. 인증 없이 열려 있는 경로다.
//
// 토큰이 없으므로 JWT 필터와 bcrypt 가 끼지 않는다. 다른 측정에서 인증 비용이
// 얼마나 섞여 있었는지 가늠하는 기준선이 된다.
//
// keyword_metrics 는 (keyword_id, period) 가 유니크지만 이 조회는 반대 방향이다.
// 분야와 유형으로 거르고 순위로 정렬한다. 그쪽을 받쳐 주는 인덱스는 없다.

import { check } from 'k6';
import { BASE_URL, arrivalRate, baseThresholds } from '../lib/config.js';
import { anonGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 50);

const LIST = 'GET /trends';

const DOMAINS = ['DEVELOP', 'FASHION'];
const TYPES = ['CURRENT', 'RISING', 'NEW'];
const PERIODS = ['24H', '7D', '30D'];

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${LIST}}`]: ['p(95)<500'],
  },
};

export default function () {
  // 한 조합만 계속 치면 공유 버퍼에 그 페이지만 남아 실제보다 빨라진다.
  const n = __ITER * 3 + __VU;
  const domain = DOMAINS[n % DOMAINS.length];
  const type = TYPES[n % TYPES.length];
  const period = PERIODS[n % PERIODS.length];

  const res = anonGet(
    `${BASE_URL}/trends?domain=${domain}&type=${type}&period=${period}&page=0&size=20`,
    LIST,
  );
  check(res, { '트렌드 목록 200': (r) => r.status === 200 });
}
