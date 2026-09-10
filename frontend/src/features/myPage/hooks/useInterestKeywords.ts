import { useCallback, useSyncExternalStore } from 'react';
import {
  defaultAlerts,
  getInterestKeywordState,
  setInterestKeywordState,
  subscribeInterestKeywordState,
} from '../api/interestKeywordStorage';
import type { InterestKeyword, InterestKeywordState, KeywordAlerts } from '../types/myPage';

interface AddKeywordInput {
  keyword: string;
  trendId?: string;
}

interface AddKeywordResult {
  keyword: InterestKeyword;
  added: boolean;
}

export function useInterestKeywords() {
  const state = useSyncExternalStore(subscribeInterestKeywordState, getInterestKeywordState);

  const update = useCallback((next: (current: InterestKeywordState) => InterestKeywordState) => {
    const current = getInterestKeywordState();
    const value = next(current);
    if (value !== current) setInterestKeywordState(value);
  }, []);

  /** 이미 등록한 키워드면 그대로 두고, 등록했는지 여부를 함께 알려줍니다. */
  const addKeyword = useCallback(({ keyword, trendId }: AddKeywordInput): AddKeywordResult | undefined => {
    const name = keyword.trim();
    if (!name) return undefined;
    const current = getInterestKeywordState();
    const existing = current.keywords.find((item) => (trendId ? item.trendId === trendId : item.keyword === name));
    if (existing) return { keyword: existing, added: false };
    const added: InterestKeyword = {
      keywordId: `keyword-${Date.now().toString(36)}`,
      keyword: name,
      trendId,
      alerts: defaultAlerts,
    };
    // 방금 등록한 키워드를 바로 확인할 수 있도록 목록 맨 위에 올립니다.
    update((value) => ({ keywords: [added, ...value.keywords] }));
    return { keyword: added, added: true };
  }, [update]);

  const removeKeyword = useCallback((keywordId: string) => {
    update((current) => ({ keywords: current.keywords.filter((keyword) => keyword.keywordId !== keywordId) }));
  }, [update]);

  const setAlerts = useCallback((keywordId: string, alerts: Partial<KeywordAlerts>) => {
    update((current) => ({
      keywords: current.keywords.map((keyword) =>
        (keyword.keywordId === keywordId ? { ...keyword, alerts: { ...keyword.alerts, ...alerts } } : keyword)),
    }));
  }, [update]);

  /** 끌어온 키워드를 대상 키워드의 앞(또는 뒤)에 끼워 넣습니다. */
  const moveKeyword = useCallback((keywordId: string, targetKeywordId: string, after: boolean) => {
    if (keywordId === targetKeywordId) return;
    update((current) => {
      const from = current.keywords.findIndex((keyword) => keyword.keywordId === keywordId);
      if (from < 0) return current;
      const next = [...current.keywords];
      const [moved] = next.splice(from, 1);
      const targetIndex = next.findIndex((keyword) => keyword.keywordId === targetKeywordId);
      const to = targetIndex < 0 ? next.length : targetIndex + (after ? 1 : 0);
      next.splice(to, 0, moved);
      return { keywords: next };
    });
  }, [update]);

  /** 메뉴에서 한 칸씩 옮기는 경로. 끌어 옮기기를 쓰기 어려운 경우를 위한 것입니다. */
  const shiftKeyword = useCallback((keywordId: string, offset: number) => {
    update((current) => {
      const from = current.keywords.findIndex((keyword) => keyword.keywordId === keywordId);
      const to = from + offset;
      if (from < 0 || to < 0 || to >= current.keywords.length) return current;
      const next = [...current.keywords];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return { keywords: next };
    });
  }, [update]);

  return { keywords: state.keywords, addKeyword, removeKeyword, setAlerts, moveKeyword, shiftKeyword };
}
