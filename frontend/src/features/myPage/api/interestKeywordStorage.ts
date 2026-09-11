import type { InterestKeyword, InterestKeywordState, KeywordAlerts } from '../types/myPage';

const keywordStateKey = 'trendin-interest-keywords-v1';

const emptyKeywordState: InterestKeywordState = { keywords: [] };

/** 새로 등록한 키워드는 알림을 켜지 않은 상태에서 시작합니다. */
export const defaultAlerts: KeywordAlerts = { trend: false, weekly: false };

function parseAlerts(value: unknown): KeywordAlerts {
  if (!value || typeof value !== 'object') return defaultAlerts;
  const alerts = value as Partial<KeywordAlerts>;
  return { trend: alerts.trend === true, weekly: alerts.weekly === true };
}

function parseKeywords(value: unknown): InterestKeyword[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((keyword): keyword is InterestKeyword =>
      Boolean(keyword) && typeof keyword === 'object'
      && typeof (keyword as InterestKeyword).keywordId === 'string'
      && typeof (keyword as InterestKeyword).keyword === 'string')
    .map((keyword) => ({
      keywordId: keyword.keywordId,
      keyword: keyword.keyword,
      trendId: typeof keyword.trendId === 'string' ? keyword.trendId : undefined,
      alerts: parseAlerts(keyword.alerts),
    }));
}

function readInterestKeywordState(): InterestKeywordState {
  try {
    const raw = window.localStorage.getItem(keywordStateKey);
    if (!raw) return emptyKeywordState;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return emptyKeywordState;
    return { keywords: parseKeywords((parsed as InterestKeywordState).keywords) };
  } catch {
    return emptyKeywordState;
  }
}

/*
 * 사이드바의 요약 숫자와 키워드 목록이 같은 상태를 봐야 하므로, 훅마다 useState를 두지 않고
 * 모듈 하나에 담아 구독합니다. 저장 보드(savedBoardStorage)와 같은 방식입니다.
 */
let cachedState: InterestKeywordState | undefined;
const listeners = new Set<() => void>();

export function getInterestKeywordState(): InterestKeywordState {
  cachedState ??= readInterestKeywordState();
  return cachedState;
}

export function setInterestKeywordState(state: InterestKeywordState) {
  cachedState = state;
  try {
    window.localStorage.setItem(keywordStateKey, JSON.stringify(state));
  } catch {
    // Device-local storage may be unavailable in private browsing.
  }
  listeners.forEach((listener) => listener());
}

export function subscribeInterestKeywordState(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
