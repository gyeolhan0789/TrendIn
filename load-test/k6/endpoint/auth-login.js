// 로그인. 다른 스크립트가 일부러 피해 간 비용을 여기서만 잰다.
//
// 비밀번호 인코더는 bcrypt strength 10 이다. 해시 한 번이 수십 밀리초의 CPU 를
// 쓰고, 그 시간은 데이터 양과 무관하다. 인덱스로 줄일 수 있는 종류가 아니라서
// 다른 조회와 섞으면 원인을 가린다.
//
// 목표 도착률을 낮게 잡는다. 같은 EC2 에서 k6 도 돌기 때문에, 높게 잡으면 서버가
// 아니라 호스트 CPU 가 먼저 마른다. Grafana 의 CPU 패널에서 프로세스는 여유가
// 있는데 시스템만 1 에 붙으면 그 상태다.
//
// 로그인은 Redis 에 리프레시 토큰을 쓴다. 조회 전용 측정과 달리 쓰기가 섞인다.

import { check } from 'k6';
import http from 'k6/http';
import { BASE_URL, PASSWORD, MEMBER_COUNT, arrivalRate, baseThresholds } from '../lib/config.js';

const PEAK_RPS = Number(__ENV.PEAK_RPS || 30);

const LOGIN = 'POST /auth/login';

export const options = {
  scenarios: { load: arrivalRate(PEAK_RPS) },
  thresholds: {
    ...baseThresholds,
    [`http_req_duration{name:${LOGIN}}`]: ['p(95)<2000'],
  },
};

export default function () {
  // 같은 계정만 치면 어떤 계층이 캐시를 도와줄 수 있다. 회원을 골고루 돈다.
  const id = 1 + ((__ITER * 17 + __VU) % MEMBER_COUNT);

  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: `load${id}@test.com`, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: LOGIN } },
  );

  check(res, {
    '로그인 200': (r) => r.status === 200,
    '토큰 발급됨': (r) => r.status === 200 && !!r.json('data.accessToken'),
  });
}
