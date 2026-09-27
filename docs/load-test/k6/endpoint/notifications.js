// 알림 목록과 안 읽은 개수. 이 시드에서 가장 먼저 무너질 곳으로 본다.
//
// notifications 에는 member_id 인덱스가 없다. 유니크 제약은 dedup_key 하나뿐이고,
// 외래키는 인덱스를 만들어 주지 않는다. 66만 행에서 member_id 로 거르면 전체를
// 훑어야 한다. 헤더에 늘 붙어 있는 안 읽은 개수 조회까지 같은 비용을 낸다.
//
// 알림이 1,500건 쌓인 헤비 회원으로 잰다. 평균 회원만 재면 문제가 드러나지 않는다.

import { check } from 'k6';
import { BASE_URL, heavyMemberId, arrivalRate, baseThresholds } from '../lib/config.js';
import { tokensFor, pickToken, authGet } from '../lib/auth.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 20);
const TOKEN_POOL = Number(__ENV.TOKEN_POOL || 50);

const LIST = 'GET /members/me/notifications';
const UNREAD = 'GET /members/me/notifications/unread-count';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    // 엔드포인트마다 임계값을 걸어야 요약에 따로 출력된다. 숫자 자체보다
    // 둘을 갈라 보는 것이 목적이다.
    [`http_req_duration{name:${LIST}}`]: ['p(95)<1000'],
    [`http_req_duration{name:${UNREAD}}`]: ['p(95)<500'],
  },
};

export function setup() {
  return { tokens: tokensFor(heavyMemberId, TOKEN_POOL) };
}

// 한 번 돌 때 요청 두 개다. 목표 도착률의 두 배가 실제 초당 요청 수가 된다.
export default function (data) {
  const token = pickToken(data.tokens);

  const list = authGet(`${BASE_URL}/members/me/notifications?page=0&size=20`, token, LIST);
  check(list, { '알림 목록 200': (r) => r.status === 200 });

  const unread = authGet(`${BASE_URL}/members/me/notifications/unread-count`, token, UNREAD);
  check(unread, { '안 읽은 개수 200': (r) => r.status === 200 });
}
