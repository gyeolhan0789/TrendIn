import type { RegionPeriodCode } from '../../../constants/filterCodes';

/*
 * 나라와 트렌드는 같은 표를 양쪽에서 읽습니다. 트렌드를 고르면 나라별 언급량이 나오고,
 * 나라를 고르면 그 나라에서 많이 언급된 트렌드가 나옵니다. 둘은 같은 구간을 보므로 숫자가 맞습니다.
 *
 * 확산 경로만 예외입니다. 늘 30일을 보므로, 24시간이나 7일 순위에 없는 나라가 경로에는
 * 있을 수 있습니다. 최근에 잠잠해진 나라입니다.
 */

/** 나라 하나의 언급량. 순위는 언급량이 같으면 같은 등수를 받습니다. */
export interface TrendRegion {
  rank: number;
  /** ISO 3166-1 alpha-2. 파이프라인이 나라를 가리지 못하면 XX 가 옵니다. */
  countryCode: string;
  /** 서버가 한국어로 지어 줍니다. 아는 나라가 아니면 코드가 그대로 옵니다. */
  countryName: string;
  mentionCount: number;
}

export interface TrendRegionList {
  trendId: number;
  period: RegionPeriodCode;
  timezone: string;
  /** 집계 구간. Asia/Seoul 기준 날짜이고 끝 날짜는 포함하지 않습니다. */
  startDate: string;
  endDate: string;
  /** 언급량이 많은 순서. 자료가 아직 없으면 비어 옵니다. */
  regions: TrendRegion[];
}

/**
 * 한 분야를 나라별로 갈라 본 언급량입니다. 트렌드를 고르지 않아도 지도를 칠할 수 있습니다.
 * 줄 모양은 {@link TrendRegion} 과 같아, 지도에 올릴 때 두 조회를 갈라 다룰 필요가 없습니다.
 */
export interface CountryRegionList {
  domain: string;
  period: RegionPeriodCode;
  timezone: string;
  startDate: string;
  endDate: string;
  /** 나라를 가리지 않은 전체 언급량. 나라별 몫을 내는 분모입니다. */
  totalMentionCount: number;
  countries: TrendRegion[];
}

/** 나라 하나에서 많이 언급된 트렌드 한 줄. */
export interface CountryTrend {
  rank: number;
  /** 아직 트렌드로 묶이지 않은 키워드는 비어 옵니다. 그런 줄은 상세로 갈 수 없습니다. */
  trendId: number | null;
  keywordId: number;
  keyword: string;
  mentionCount: number;
}

export interface CountryTrendList {
  domain: string;
  countryCode: string;
  countryName: string;
  period: RegionPeriodCode;
  timezone: string;
  startDate: string;
  endDate: string;
  /** 잘라 내기 전 이 나라의 전체 언급량. TOP 5 만 받아도 몫이 제대로 나옵니다. */
  totalMentionCount: number;
  trends: CountryTrend[];
}

/** 한 나라에서 처음 잡힌 날. order 는 1부터이고 날짜가 이른 순서입니다. */
export interface TrendJourneyStop {
  countryCode: string;
  countryName: string;
  firstDetectedDate: string;
  order: number;
}

export interface TrendRegionJourney {
  trendId: number;
  /** 늘 30D 입니다. 서버가 기간을 받지 않습니다. */
  period: string;
  timezone: string;
  startDate: string;
  endDate: string;
  /** 퍼져 나간 순서. 30일 안에 언급이 한 번이라도 잡힌 나라만 들어옵니다. */
  regions: TrendJourneyStop[];
}
