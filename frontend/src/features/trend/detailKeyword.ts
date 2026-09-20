import type { KeywordSearchItem } from './types/keyword';

export type DetailKeywordSearchItem = KeywordSearchItem & { trendId: number };

/** 검색 결과에 실제로 열 수 있는 상세가 연결되어 있는지 판정합니다. */
export function isDetailKeyword(item: KeywordSearchItem): item is DetailKeywordSearchItem {
  return Number.isInteger(item.trendId) && (item.trendId ?? 0) > 0;
}

/** 상세 화면으로 이동할 수 있는 검색 결과만 남깁니다. */
export function filterDetailKeywords(items: readonly KeywordSearchItem[]): DetailKeywordSearchItem[] {
  return items.filter(isDetailKeyword);
}
