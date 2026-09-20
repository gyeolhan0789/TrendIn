import assert from 'node:assert/strict';
import test, { afterEach, beforeEach, mock } from 'node:test';
import { registerHooks } from 'node:module';
import axios, { AxiosError } from 'axios';

/*
 * src 는 번들러가 확장자를 붙여 주는 것을 전제로 쓰였습니다. 노드는 그러지 않아서,
 * 상대 경로가 그대로 풀리지 않으면 .ts 를 붙여 한 번 더 봐 줍니다.
 */
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (!specifier.startsWith('.')) return nextResolve(specifier, context);
    try {
      return nextResolve(specifier, context);
    } catch {
      return nextResolve(`${specifier}.ts`, context);
    }
  },
});

const store = new Map();
globalThis.window = {
  localStorage: {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key),
  },
  // clearAuthSession 이 랜딩 안내 표시를 함께 되돌리므로 이쪽도 흉내 냅니다.
  sessionStorage: {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  },
  addEventListener: () => {},
};

/*
 * 서버를 세우는 대신 어댑터를 바꿔 끼웁니다. 인스턴스를 만들 때의 기본값을 물려받으므로,
 * 인터셉터가 붙지 않아 밖에서 잡을 수 없는 재발급 전용 인스턴스까지 함께 덮입니다.
 */
let handle = () => { throw new Error('요청이 예상되지 않았습니다.'); };
axios.defaults.adapter = async (config) => handle(config);

const { apiClient } = await import('../src/api/client.ts');
const { clearAuthSession, getAuthSession, setAuthSession } = await import('../src/features/auth/api/authSessionStorage.ts');

const GRACE_MS = 3_000;

function reply(config, status, data) {
  const response = { data, status, statusText: '', headers: {}, config, request: {} };
  if (status < 400) return response;
  throw new AxiosError('요청 실패', String(status), config, {}, response);
}

/** 연결 자체가 닿지 않은 실패입니다. 타임아웃과 끊긴 연결이 이 모양으로 옵니다. */
function unreachable(config) {
  throw new AxiosError('timeout of 10000ms exceeded', AxiosError.ECONNABORTED, config, {});
}

function signIn() {
  setAuthSession({
    accessToken: 'AT1',
    refreshToken: 'RT1',
    tokenType: 'Bearer',
    email: 'me@trendin.dev',
    onboardingCompleted: true,
  });
}

beforeEach(() => {
  mock.timers.enable({ apis: ['setTimeout'] });
  signIn();
});

afterEach(() => {
  // 재발급 결과를 잠시 들고 있으므로, 다음 시험이 앞 시험의 결과를 물려받지 않게 창을 넘깁니다.
  mock.timers.tick(GRACE_MS + 1);
  mock.timers.reset();
  clearAuthSession();
  store.clear();
});

test('재발급이 서버에 닿지 못했으면 세션을 버리지 않는다', async () => {
  handle = (config) => (config.url === '/auth/reissue' ? unreachable(config) : reply(config, 401, null));

  await assert.rejects(apiClient.get('/members/me/interest-keywords'));

  // 잠깐 끊긴 것뿐인데 로그아웃시키면, 멀쩡한 14일짜리 세션을 네트워크 사정으로 버리게 됩니다.
  assert.ok(getAuthSession(), '세션이 남아 있어야 합니다');
  assert.equal(getAuthSession()?.refreshToken, 'RT1');
});

test('서버가 Refresh Token을 거절했으면 세션을 버린다', async () => {
  handle = (config) => reply(config, 401, null);

  await assert.rejects(apiClient.get('/members/me/interest-keywords'));

  assert.equal(getAuthSession(), undefined);
});

test('새 토큰으로 다시 물어도 401이면 세션을 비워 로그인으로 보낸다', async () => {
  handle = (config) => {
    if (config.url === '/auth/reissue') {
      return reply(config, 200, { data: { accessToken: 'AT2', refreshToken: 'RT2', tokenType: 'Bearer', onboardingCompleted: true } });
    }
    return reply(config, 401, null);
  };

  await assert.rejects(apiClient.get('/members/me/interest-keywords'));

  // 세션을 남겨 두면 RequireAuth 가 움직이지 않아, 화면은 401만 되풀이하며 그 자리에 머뭅니다.
  assert.equal(getAuthSession(), undefined);
});

test('한꺼번에 몰린 401도, 뒤늦게 도착한 401도 재발급을 한 번만 부른다', async () => {
  let reissues = 0;
  handle = (config) => {
    if (config.url === '/auth/reissue') {
      reissues += 1;
      assert.equal(JSON.parse(config.data).refreshToken, 'RT1');
      return reply(config, 200, { data: { accessToken: 'AT2', refreshToken: 'RT2', tokenType: 'Bearer', onboardingCompleted: true } });
    }
    if (config.headers.Authorization !== 'Bearer AT2') return reply(config, 401, null);
    return reply(config, 200, { data: [] });
  };

  // 관심 키워드 화면이 뜨자마자 함께 나가는 세 갈래입니다.
  await Promise.all([
    apiClient.get('/members/me/interest-keywords'),
    apiClient.get('/members/me/recommended-keywords'),
    apiClient.get('/members/me/notifications/unread-count'),
  ]);
  assert.equal(reissues, 1);

  /*
   * 재발급 전에 이미 나가 있던 요청은 옛 토큰을 단 채 조금 늦게 401로 돌아옵니다.
   * 여기서 또 재발급을 걸면 방금 회전시킨 토큰을 다시 보내게 됩니다.
   */
  await apiClient.get('/keywords/search', { headers: { Authorization: 'Bearer AT1' } });
  assert.equal(reissues, 1);
  assert.equal(getAuthSession()?.refreshToken, 'RT2');
});
test('로그아웃이 401로 끝나도 세션을 먼저 지우지 않는다', async () => {
  handle = (config) => {
    if (config.url === '/auth/reissue') {
      return reply(config, 200, { data: { accessToken: 'AT2', refreshToken: 'RT2', tokenType: 'Bearer', onboardingCompleted: true } });
    }
    return reply(config, 401, null);
  };

  await assert.rejects(apiClient.post('/auth/logout', { refreshToken: 'RT1' }));

  /*
   * 서버는 회전된 토큰만 쥐고 있습니다. 여기서 세션을 지워 버리면 화면이 그 토큰을 다시 보낼
   * 수 없어, 기기에서만 로그아웃되고 서버에는 쓸 수 있는 Refresh Token이 남습니다.
   */
  assert.equal(getAuthSession()?.refreshToken, 'RT2');
});
