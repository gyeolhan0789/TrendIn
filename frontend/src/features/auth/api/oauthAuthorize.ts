/*
 * 제공자 인가 화면으로 보내는 쪽입니다. 코드를 토큰으로 바꾸는 일은 서버가 하고,
 * 화면은 일회용 인가 코드를 받아 오기까지만 맡습니다.
 *
 * state 는 서버가 대조하지 않습니다. 인가 URL 을 만드는 쪽이 화면이라 서버는 발급한 state 를
 * 알지 못하기 때문입니다. 그래서 만든 쪽이 콜백에서 직접 맞춰 봐야 하고, 그 짝을 이 파일이 맡습니다.
 * 보내기 전에 stateOf 로 심고, 돌아온 뒤 consumeOAuthState 로 꺼내 비교합니다.
 */

export const GITLAB_PROVIDER = 'gitlab';

/** 서버가 /api/v4/user 만 부르므로 사용자 정보를 읽을 권한 하나로 충분합니다. */
const GITLAB_SCOPE = 'read_user';

const statePrefix = 'trendin-oauth-state-v1.';

/** 설정이 비어 시작조차 못 하는 경우입니다. 화면이 사용자에게 보여 줄 문구를 담아 던집니다. */
export class OAuthStartError extends Error {}

interface ProviderConfig {
  /** 제공자 인스턴스 주소. 사내 GitLab 과 gitlab.com 이 같은 규약을 써서 주소만 다릅니다. */
  baseUrl: string;
  clientId: string;
  /** 제공자에 등록한 값·백엔드 설정과 글자 하나까지 같아야 토큰 교환이 통과합니다. */
  redirectUri: string;
  scope: string;
}

function callbackPath(provider: string): string {
  return `/oauth/${provider}/callback`;
}

/*
 * 되돌아올 주소를 설정에서 받되, 비었으면 지금 열려 있는 주소에서 짓습니다.
 * 로컬(5173)과 배포를 한 값으로 묶어 두면 한쪽이 반드시 어긋나기 때문입니다.
 */
function gitlabConfig(): ProviderConfig {
  const env = import.meta.env;
  return {
    baseUrl: stripTrailingSlash(env.VITE_GITLAB_OAUTH_BASE_URL ?? 'https://lab.ssafy.com'),
    clientId: (env.VITE_GITLAB_OAUTH_CLIENT_ID ?? '').trim(),
    redirectUri: (env.VITE_GITLAB_OAUTH_REDIRECT_URI ?? '').trim()
      || `${window.location.origin}${callbackPath(GITLAB_PROVIDER)}`,
    scope: GITLAB_SCOPE,
  };
}

function stripTrailingSlash(value: string): string {
  const trimmed = value.trim();
  return trimmed.endsWith('/') ? trimmed.slice(0, -1) : trimmed;
}

function configOf(provider: string): ProviderConfig {
  if (provider === GITLAB_PROVIDER) return gitlabConfig();
  throw new OAuthStartError('지원하지 않는 로그인 방식입니다.');
}

/*
 * 추측할 수 없는 값이어야 해서 Math.random 이 아니라 암호용 난수를 씁니다.
 * 이 값이 곧 '이 로그인을 시작한 것이 이 브라우저'라는 증거입니다.
 */
function createState(): string {
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

/*
 * 탭마다 따로 담기는 sessionStorage 에 둡니다. 로그인을 시작한 탭으로 돌아오므로 값이 남아 있고,
 * 다른 탭이나 다음 방문에는 새지 않습니다.
 */
function rememberState(provider: string, state: string) {
  try {
    window.sessionStorage.setItem(statePrefix + provider, state);
  } catch {
    // 저장을 못 하면 돌아왔을 때 맞춰 볼 값이 없어 로그인이 막힙니다. 떠나기 전에 멈춥니다.
    throw new OAuthStartError('브라우저 저장소를 쓸 수 없어 로그인을 시작하지 못했습니다. 시크릿 모드라면 일반 창에서 시도해 주세요.');
  }
}

/** 한 번 쓰고 지웁니다. 남겨 두면 다음 콜백이 옛 값으로도 통과합니다. */
export function consumeOAuthState(provider: string): string | undefined {
  const key = statePrefix + provider;
  try {
    const stored = window.sessionStorage.getItem(key);
    window.sessionStorage.removeItem(key);
    return stored ?? undefined;
  } catch {
    return undefined;
  }
}

/**
 * 제공자 인가 화면으로 떠납니다. 정상이면 이 호출 뒤 코드가 이어지지 않습니다.
 * 설정이 비었거나 저장소를 못 쓰면 떠나지 않고 OAuthStartError 를 던집니다.
 */
export function startOAuthLogin(provider: string): void {
  const config = configOf(provider);
  if (!config.clientId) {
    throw new OAuthStartError('GitLab 로그인이 아직 설정되지 않았습니다. 관리자에게 문의해 주세요.');
  }

  const state = createState();
  rememberState(provider, state);

  const authorizeUrl = new URL(`${config.baseUrl}/oauth/authorize`);
  authorizeUrl.searchParams.set('client_id', config.clientId);
  authorizeUrl.searchParams.set('redirect_uri', config.redirectUri);
  authorizeUrl.searchParams.set('response_type', 'code');
  authorizeUrl.searchParams.set('state', state);
  authorizeUrl.searchParams.set('scope', config.scope);

  window.location.assign(authorizeUrl.toString());
}
