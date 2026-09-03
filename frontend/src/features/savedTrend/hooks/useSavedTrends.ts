import { useQuery } from '@tanstack/react-query';
import { getSavedTrends } from '../api/savedTrendApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useSavedTrends() {
  return useQuery({ queryKey: queryKeys.savedTrends.all, queryFn: getSavedTrends });
}

