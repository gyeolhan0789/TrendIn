import type { TrendDomainRef, TrendType } from './trend';

export interface KeywordSearchItem {
  keywordId: number;
  keyword: string;
  domain: TrendDomainRef;
  /** 아직 트렌드에 오르지 않은 키워드는 비어 있습니다. */
  trendId: number | null;
  trendTypes: TrendType[];
  growthRate: number | null;
}

export interface KeywordSearchResult {
  items: KeywordSearchItem[];
  hasNext: boolean;
}
