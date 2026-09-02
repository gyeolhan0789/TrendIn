import { useQuery } from '@tanstack/react-query';
import { getTrendDetail } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useTrendDetail(trendId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.detail(trendId ?? ''),
    queryFn: () => getTrendDetail(trendId as string),
    enabled: Boolean(trendId),
  });
}
