import http from 'k6/http';
import { BASE_URL, PASSWORD } from './config.js';

// VU 마다 로그인시키면 안 된다.
//
// 비밀번호 인코더가 bcrypt strength 10 이라 검증 한 번에 CPU 를 꽤 쓴다. 수백
// VU 가 동시에 로그인하면 CPU 가 해싱으로 차고, 뒤따르는 조회 API 가 전부 느려진다.
// 그러면 "알림 조회가 느리다"는 결과가 나오는데 원인은 로그인이다. 실제 사용자는
// 15분짜리 액세스 토큰을 받아 그 안에서 여러 번 조회하므로, 그 모양을 흉내낸다.
//
// 로그인 자체의 비용은 endpoint/auth-login.js 에서 따로 잰다.
export function issueTokens(memberIds) {
  const tokens = [];
  for (const id of memberIds) {
    const res = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ email: `load${id}@test.com`, password: PASSWORD }),
      { headers: { 'Content-Type': 'application/json' }, tags: { name: 'setup:login' } },
    );
    if (res.status !== 200) {
      throw new Error(
        `토큰 발급 실패 (load${id}@test.com): HTTP ${res.status} ${String(res.body).slice(0, 200)}`,
      );
    }
    const token = res.json('data.accessToken');
    if (!token) {
      throw new Error(`응답에 accessToken 이 없다: ${String(res.body).slice(0, 200)}`);
    }
    tokens.push(token);
  }
  return tokens;
}

export function tokensFor(idFn, count) {
  const ids = [];
  for (let i = 0; i < count; i++) {
    ids.push(idFn(i));
  }
  return issueTokens(ids);
}

export function pickToken(tokens) {
  return tokens[__VU % tokens.length];
}

// URL 에 id 가 들어가면 경로마다 다른 지표가 되어 집계가 흩어진다. name 태그로
// 논리적인 엔드포인트를 묶어야 p95 를 엔드포인트 단위로 읽을 수 있다.
export function authGet(url, token, name) {
  return http.get(url, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { name },
  });
}

export function anonGet(url, name) {
  return http.get(url, { tags: { name } });
}
