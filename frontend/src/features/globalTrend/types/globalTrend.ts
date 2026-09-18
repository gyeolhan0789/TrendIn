import type { RegionPeriodCode } from '../../../constants/filterCodes';

/*
 * 트렌드가 어느 나라에서 얼마나 언급됐고, 어느 나라에서 먼저 잡혔는지입니다.
 *
 * 두 조회가 보는 구간이 다릅니다. 나라별 순위는 고른 기간(24H·7D)을 보고, 확산 경로는 늘
 * 30일을 봅니다. 그래서 순위에 없는 나라가 경로에는 있을 수 있습니다. 최근에 잠잠해진 나라입니다.
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
