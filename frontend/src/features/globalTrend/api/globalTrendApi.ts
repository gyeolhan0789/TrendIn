import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { RegionPeriodCode } from '../../../constants/filterCodes';
import type {
  CountryRegionList,
  CountryTrendList,
  TrendRegionJourney,
  TrendRegionList,
} from '../types/globalTrend';

/** 트렌드 하나가 나라별로 얼마나 언급됐는지 가져옵니다. 세 기간을 모두 받습니다. */
export async function getTrendRegions(trendId: number, period: RegionPeriodCode): Promise<TrendRegionList> {
  return unwrap(apiClient.get<ApiResponse<TrendRegionList>>(API_ENDPOINTS.trends.regions(trendId), {
    params: { period },
  }));
}

/**
 * 한 분야를 나라별로 갈라 언급량이 많은 차례로 가져옵니다.
 * 트렌드를 고르기 전에도 지도를 칠할 수 있어야 해서 트렌드를 받지 않습니다.
 */
export async function getRegionCountries(domain: string, period: RegionPeriodCode): Promise<CountryRegionList> {
  return unwrap(apiClient.get<ApiResponse<CountryRegionList>>(API_ENDPOINTS.regions.list, {
    params: { domain, period },
  }));
}

/** 나라 하나에서 많이 언급된 트렌드를 가져옵니다. size 는 받아 올 줄 수입니다. */
export async function getCountryTrends(
  domain: string,
  countryCode: string,
  period: RegionPeriodCode,
  size: number,
): Promise<CountryTrendList> {
  return unwrap(apiClient.get<ApiResponse<CountryTrendList>>(
    API_ENDPOINTS.regions.trends(countryCode), { params: { domain, period, size } },
  ));
}

/**
 * 나라별 최초 감지일을 이른 순서로 가져옵니다. 이 순서가 곧 트렌드가 퍼져 나간 길입니다.
 * 기간을 받지 않고 늘 30일을 보므로, 나라별 순위와 구간이 어긋날 수 있습니다.
 */
export async function getTrendRegionJourney(trendId: number): Promise<TrendRegionJourney> {
  return unwrap(
    apiClient.get<ApiResponse<TrendRegionJourney>>(API_ENDPOINTS.trends.regionJourney(trendId)),
  );
}
