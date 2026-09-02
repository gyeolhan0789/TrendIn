export interface Trend {
  trendId: string;
  keyword: string;
  category: string;
  mentionCount: number;
  growthRate: number;
  description?: string;
  tag?: string;
  kind?: 'top' | 'new' | 'rising';
  period?: string;
  change?: number | 'NEW';
}

export interface TrendDetail extends Trend {
  updatedAt?: string;
}

export interface TrendAnalysis {
  trendId: string;
  description: string;
}

export interface RelatedKeyword {
  keywordId?: string;
  keyword: string;
  relevance?: number;
}

export interface TrendContent {
  contentId: string;
  title: string;
  url: string;
  source?: string;
  publishedAt?: string;
}

export interface TrendFilterParams {
  category?: string;
  period?: string;
}
