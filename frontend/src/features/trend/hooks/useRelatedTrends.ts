import { useQuery } from '@tanstack/react-query';
import { getRelatedTrends } from '../api/trendApi';
import type { TrendFilterParams } from '../types/trend';
import { queryKeys } from '../../../utils/queryKeys';

export function useRelatedTrends(params?: TrendFilterParams) {
  return useQuery({ queryKey: queryKeys.trends.related(params), queryFn: () => getRelatedTrends(params) });
}

