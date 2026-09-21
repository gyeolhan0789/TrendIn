// 트렌드에 딸린 콘텐츠 목록. 인증 없이 열려 있다.
//
// keyword_contents 의 기본키가 (content_id, keyword_id) 다. 이 조회는 keyword_id
// 하나로 찾으므로 기본키의 선두 컬럼을 쓰지 못한다. 60만 행에서 전체를 훑을
// 가능성이 높고, 콘텐츠의 70% 를 상위 2,000 개 키워드에 몰아 두었으므로 그
// 키워드를 고르면 읽을 행도 많다.

import { check } from 'k6';
import { BASE_URL, hotTrendId, arrivalRate, baseThresholds } from '../lib/config.js';
import { anonGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 30);

const CONTENTS = 'GET /trends/{id}/contents';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${CONTENTS}}`]: ['p(95)<1000'],
  },
};

export default function () {
  const id = hotTrendId(__ITER * 13 + __VU);
  const res = anonGet(`${BASE_URL}/trends/${id}/contents?page=0&size=10`, CONTENTS);
  check(res, { '콘텐츠 목록 200': (r) => r.status === 200 });
}
