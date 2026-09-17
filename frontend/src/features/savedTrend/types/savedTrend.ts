import type { TrendDomainRef, TrendType } from '../../trend/types/trend';

/**
 * 저장한 트렌드 한 건입니다.
 * 지우거나 이미 담았는지 가릴 때 쓰는 키는 trendId 가 아니라 savedTrendId 입니다.
 */
export interface SavedTrend {
  savedTrendId: number;
  trendId: number;
  keywordId: number;
  keyword: string;
  domain: TrendDomainRef;
  trendTypes: TrendType[];
  description: string | null;
  /** 요청한 기간의 지표가 없으면 비어 옵니다. */
  mentionCount: number | null;
  growthRate: number | null;
  savedAt: string;
}

export interface SavedTrendList {
  trends: SavedTrend[];
  hasNext: boolean;
}
