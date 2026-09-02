import { useQuery } from '@tanstack/react-query';
import { getNewTrends } from '../api/trendApi';
import type { TrendFilterParams } from '../types/trend';
import { queryKeys } from '../../../utils/queryKeys';

export function useNewTrends(params?: TrendFilterParams) {
  return useQuery({ queryKey: queryKeys.trends.new(params), queryFn: () => getNewTrends(params) });
}

