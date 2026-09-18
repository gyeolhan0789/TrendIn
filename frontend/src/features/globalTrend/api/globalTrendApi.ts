import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { RegionPeriodCode } from '../../../constants/filterCodes';
import type { TrendRegionJourney, TrendRegionList } from '../types/globalTrend';

/**
 * 트렌드가 나라별로 얼마나 언급됐는지 가져옵니다.
 *
 * 기간은 24H 나 7D 만 받습니다. 30D 를 보내면 서버가 거절하므로 부르는 쪽이 그 둘로 좁혀야 합니다.
 */
export async function getTrendRegions(trendId: number, period: RegionPeriodCode): Promise<TrendRegionList> {
  return unwrap(apiClient.get<ApiResponse<TrendRegionList>>(API_ENDPOINTS.trends.regions(trendId), {
    params: { period },
  }));
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
