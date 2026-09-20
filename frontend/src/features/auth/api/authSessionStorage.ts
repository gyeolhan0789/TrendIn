import type { AuthSession, AuthTokenBundle } from '../types/auth';
import { resetLandingGuide } from '../../../utils/landingExperience';

const sessionKey = 'trendin-auth-session-v1';

function parseSession(value: unknown): AuthSession | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const session = value as Partial<AuthSession>;
  if (typeof session.accessToken !== 'string' || !session.accessToken) return undefined;
  if (typeof session.refreshToken !== 'string' || !session.refreshToken) return undefined;
  return {
    accessToken: session.accessToken,
    refreshToken: session.refreshToken,
    tokenType: typeof session.tokenType === 'string' && session.tokenType ? session.tokenType : 'Bearer',
    email: typeof session.email === 'string' ? session.email : '',
    onboardingCompleted: session.onboardingCompleted === true,
  };
}

function readAuthSession(): AuthSession | undefined {
  try {
    const raw = window.localStorage.getItem(sessionKey);
    if (!raw) return undefined;
    return parseSession(JSON.parse(raw));
  } catch {
    return undefined;
  }
}

/*
 * 헤더, 페이지, axios 인터셉터가 모두 같은 세션을 봐야 해서 훅마다 useState를 두지 않고
 * 모듈 하나에 담아 구독합니다. 관심 키워드(interestKeywordStorage)와 같은 방식입니다.
 */
let cachedSession: AuthSession | undefined;
let loaded = false;
const listeners = new Set<() => void>();

export function getAuthSession(): AuthSession | undefined {
  if (!loaded) {
    cachedSession = readAuthSession();
    loaded = true;
  }
  return cachedSession;
}

/*
 * useSyncExternalStore 는 값이 같으면 같은 객체가 돌아오기를 요구합니다. 저장소를 다시 읽을
 * 때마다 새 객체를 내놓으면 내용이 그대로여도 화면을 다시 그리게 됩니다.
 */
function isSameSession(a: AuthSession | undefined, b: AuthSession | undefined) {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.accessToken === b.accessToken
    && a.refreshToken === b.refreshToken
    && a.tokenType === b.tokenType
    && a.email === b.email
    && a.onboardingCompleted === b.onboardingCompleted;
}

/**
 * 저장소에 담긴 최신 세션으로 메모리 캐시를 맞춥니다.
 *
 * 리프레시 토큰은 쓰는 즉시 회전해 직전 토큰이 무효가 됩니다. 캐시는 탭마다 따로 있어서,
 * 한 탭이 재발급을 마치면 다른 탭이 든 토큰은 이미 못 쓰는 토큰입니다. 재발급 직전에
 * 저장소를 다시 읽어야 옆 탭이 갈아 끼운 토큰을 씁니다.
 */
export function syncAuthSessionFromStorage(): AuthSession | undefined {
  const stored = readAuthSession();
  loaded = true;
  if (isSameSession(stored, cachedSession)) return cachedSession;
  cachedSession = stored;
  listeners.forEach((listener) => listener());
  return cachedSession;
}

export function setAuthSession(session: AuthSession) {
  cachedSession = session;
  loaded = true;
  try {
    window.localStorage.setItem(sessionKey, JSON.stringify(session));
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
  listeners.forEach((listener) => listener());
}

/** 재발급으로 토큰만 갈아 끼웁니다. 이미 로그아웃했다면 되살리지 않습니다. */
export function replaceSessionTokens(tokens: AuthTokenBundle, onboardingCompleted: boolean): AuthSession | undefined {
  const current = getAuthSession();
  if (!current) return undefined;
  const next: AuthSession = {
    ...current,
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    tokenType: tokens.tokenType,
    onboardingCompleted,
  };
  setAuthSession(next);
  return next;
}

export function clearAuthSession() {
  cachedSession = undefined;
  loaded = true;
  try {
    window.localStorage.removeItem(sessionKey);
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
  try {
    // 다음 로그인 세션의 첫 홈 진입에서 조작 안내를 다시 보여 줍니다.
    resetLandingGuide(window.sessionStorage);
  } catch {
    // Session storage may be unavailable in private browsing.
  }
  listeners.forEach((listener) => listener());
}

export function subscribeAuthSession(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/**
 * 관심 분야를 처음 고르면 서버가 온보딩을 완료 처리하므로, 기기에 둔 세션도 함께 맞춥니다.
 * 이 값이 어긋나면 이미 끝낸 사람을 온보딩으로 다시 돌려보내게 됩니다.
 */
export function markOnboardingCompleted() {
  const current = getAuthSession();
  if (!current || current.onboardingCompleted) return;
  setAuthSession({ ...current, onboardingCompleted: true });
}

/*
 * 다른 탭이 로그인하거나 로그아웃하거나 토큰을 갈아 끼우면 알려 옵니다. 같은 탭에서 쓴 값은
 * 이 이벤트가 오지 않으므로, 쓰는 쪽이 직접 구독자에게 알립니다.
 * key 가 null 이면 저장소 전체가 비워진 경우입니다.
 */
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== null && event.key !== sessionKey) return;
    syncAuthSessionFromStorage();
  });
}
