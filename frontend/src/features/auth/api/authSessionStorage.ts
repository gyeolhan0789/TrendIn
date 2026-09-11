import type { AuthSession, AuthTokenBundle } from '../types/auth';

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
  listeners.forEach((listener) => listener());
}

export function subscribeAuthSession(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
