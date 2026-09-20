import type { KeywordSearchItem } from './types/keyword';

export type DetailKeywordSearchItem = KeywordSearchItem & { trendId: number };

/** 상세 화면으로 이동할 수 있는 검색 결과만 남깁니다. */
export function filterDetailKeywords(items: readonly KeywordSearchItem[]): DetailKeywordSearchItem[] {
  return items.filter(
    (item): item is DetailKeywordSearchItem => Number.isInteger(item.trendId) && (item.trendId ?? 0) > 0,
  );
}
