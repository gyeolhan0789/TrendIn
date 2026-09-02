import { useQuery } from '@tanstack/react-query';
import { getResurgingTrends } from '../api/trendApi';
import type { TrendFilterParams } from '../types/trend';
import { queryKeys } from '../../../utils/queryKeys';

export function useResurgingTrends(params?: TrendFilterParams) {
  return useQuery({ queryKey: queryKeys.trends.resurging(params), queryFn: () => getResurgingTrends(params) });
}

