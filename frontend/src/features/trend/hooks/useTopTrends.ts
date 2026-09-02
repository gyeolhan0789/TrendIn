import { useQuery } from '@tanstack/react-query';
import { getTopTrends } from '../api/trendApi';
import type { TrendFilterParams } from '../types/trend';
import { queryKeys } from '../../../utils/queryKeys';

export function useTopTrends(params?: TrendFilterParams) {
  return useQuery({ queryKey: queryKeys.trends.top(params), queryFn: () => getTopTrends(params) });
}

