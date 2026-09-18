import type { NotificationSettings, QuietHours } from '../types/notificationSettings';

const settingsKey = 'trendin-notification-settings-v1';

/** 처음 들어온 사람에게 보여 줄 기본값입니다. 홍보성 메일만 꺼 둡니다. */
export const defaultNotificationSettings: NotificationSettings = {
  master: true,
  trend: { surge: true, plunge: true, discovered: true, turning: true },
  email: { marketing: false, system: true },
  quiet: { enabled: false, start: '22:00', end: '08:00' },
};

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

function parseGroup<K extends string>(value: unknown, fallback: Record<K, boolean>): Record<K, boolean> {
  const stored = (value ?? {}) as Partial<Record<K, unknown>>;
  const next = { ...fallback };
  (Object.keys(fallback) as K[]).forEach((key) => {
    if (typeof stored[key] === 'boolean') next[key] = stored[key];
  });
  return next;
}

function parseQuiet(value: unknown): QuietHours {
  const stored = (value ?? {}) as Partial<QuietHours>;
  return {
    enabled: stored.enabled === true,
    // 저장된 값이 시각 모양이 아니면 <input type="time"> 이 빈 칸으로 나오므로 기본값으로 되돌립니다.
    start: typeof stored.start === 'string' && TIME.test(stored.start) ? stored.start : defaultNotificationSettings.quiet.start,
    end: typeof stored.end === 'string' && TIME.test(stored.end) ? stored.end : defaultNotificationSettings.quiet.end,
  };
}

function parseSettings(value: unknown): NotificationSettings {
  if (!value || typeof value !== 'object') return defaultNotificationSettings;
  const stored = value as Partial<NotificationSettings>;
  return {
    master: stored.master !== false,
    trend: parseGroup(stored.trend, defaultNotificationSettings.trend),
    email: parseGroup(stored.email, defaultNotificationSettings.email),
    quiet: parseQuiet(stored.quiet),
  };
}

function readSettings(): NotificationSettings {
  try {
    const raw = window.localStorage.getItem(settingsKey);
    if (!raw) return defaultNotificationSettings;
    return parseSettings(JSON.parse(raw));
  } catch {
    return defaultNotificationSettings;
  }
}

/*
 * 세션(authSessionStorage)과 같은 방식입니다. 마이페이지의 요약 스위치와 알림 설정 화면이
 * 같은 값을 봐야 해서, 화면마다 useState 를 두지 않고 모듈 하나에 담아 구독합니다.
 */
let cached: NotificationSettings | undefined;
const listeners = new Set<() => void>();

export function getNotificationSettings(): NotificationSettings {
  if (!cached) cached = readSettings();
  return cached;
}

export function setNotificationSettings(settings: NotificationSettings) {
  cached = settings;
  try {
    window.localStorage.setItem(settingsKey, JSON.stringify(settings));
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
  listeners.forEach((listener) => listener());
}

export function subscribeNotificationSettings(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/*
 * 다른 탭에서 바꾼 값도 따라갑니다. key 가 null 이면 저장소 전체가 비워진 경우입니다.
 * useSyncExternalStore 는 값이 같으면 같은 객체이기를 요구해서, 읽은 뒤 같은지 견주고
 * 달라졌을 때만 캐시를 갈아 끼웁니다.
 */
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== null && event.key !== settingsKey) return;
    const stored = readSettings();
    if (JSON.stringify(stored) === JSON.stringify(cached)) return;
    cached = stored;
    listeners.forEach((listener) => listener());
  });
}
