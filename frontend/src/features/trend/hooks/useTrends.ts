import { useQuery } from '@tanstack/react-query';
import { getTrends } from '../api/trendApi';
import type { TrendListParams } from '../types/trend';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 분야·갈래·기간이 정해져야 부를 수 있습니다. 분야 목록을 아직 못 받았으면 고를 분야가 없어 멈춰 둡니다.
 */
export function useTrends(params: TrendListParams | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.list(params),
    queryFn: () => getTrends(params as TrendListParams),
    enabled: Boolean(params),
  });
}
