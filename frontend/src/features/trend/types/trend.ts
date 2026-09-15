import type { PeriodCode } from '../../../constants/filterCodes';

/** 서버가 트렌드를 가르는 세 갈래입니다. 목록은 이 중 하나를 골라서 부릅니다. */
export const TREND_TYPES = ['CURRENT', 'NEW', 'RISING'] as const;

export type TrendType = (typeof TREND_TYPES)[number];

/**
 * 분야 코드와 표시 이름입니다.
 * 서버는 응답마다 코드 키를 domain 또는 code 로 다르게 주므로, API 계층에서 이 모양으로 맞춥니다.
 */
export interface TrendDomainRef {
  code: string;
  name: string;
}

export interface Trend {
  trendId: number;
  keywordId: number;
  keyword: string;
  description: string;
  domain: TrendDomainRef;
  /** 한 트렌드가 여러 갈래에 동시에 들 수 있습니다. */
  trendTypes: TrendType[];
  /** 언급량 순위. 순위를 매기지 않은 갈래에서는 비어 있습니다. */
  rank: number | null;
  mentionCount: number;
  previousMentionCount: number;
  growthAmount: number;
  /** 이전 구간 언급량이 없으면 증가율을 낼 수 없어 서버가 비워 둡니다. */
  growthRate: number | null;
}

/**
 * 목록이 어느 구간을 비교한 결과인지 알려 줍니다. Asia/Seoul 자정 경계이고,
 * 지금 시각이 아니라 이미 끝난 구간이라 화면에 그대로 밝혀 줄 수 있습니다.
 */
export interface TrendAnalysisWindow {
  recentStart: string;
  recentEnd: string;
  previousStart: string;
  previousEnd: string;
}

export interface TrendList {
  trends: Trend[];
  page: number;
  size: number;
  hasNext: boolean;
  analysisWindow: TrendAnalysisWindow | null;
}

export interface TrendListParams {
  domain: string;
  type: TrendType;
  period: PeriodCode;
  page?: number;
  size?: number;
}

/** 연관 키워드. 점수는 0~100 이고 높을수록 함께 언급된 정도가 큽니다. */
export interface TrendRelatedKeyword {
  keywordId: number;
  keyword: string;
  relationScore: number;
}

export interface TrendDetail {
  trendId: number;
  keywordId: number;
  keyword: string;
  description: string;
  domain: TrendDomainRef;
  trendTypes: TrendType[];
  /** 요청한 기간의 지표가 아직 쌓이지 않았으면 지표와 분석 구간이 함께 비어 옵니다. */
  mentionCount: number | null;
  previousMentionCount: number | null;
  growthAmount: number | null;
  growthRate: number | null;
  analysisWindow: TrendAnalysisWindow | null;
  /** 한 줄 요약과 배경. 아직 정리되지 않은 트렌드는 비어 있습니다. */
  summary: string | null;
  reason: string | null;
}

export interface TrendHistoryPoint {
  bucketStart: string;
  bucketEnd: string;
  mentionCount: number;
}

/**
 * 기간을 일정한 칸으로 잘라 센 언급량입니다. 칸의 폭은 서버가 기간에 맞춰 정합니다(24H는 1시간, 7D는 하루, 30D는 사흘).
 * 자료가 없는 칸도 0으로 채워 오므로 화면에서 빈자리를 메울 필요가 없습니다.
 */
export interface TrendHistory {
  trendId: number;
  period: PeriodCode;
  timezone: string;
  startAt: string;
  endAt: string;
  history: TrendHistoryPoint[];
}

export interface TrendContent {
  contentId: number;
  title: string;
  source: string;
  url: string;
  publishedAt: string;
}
