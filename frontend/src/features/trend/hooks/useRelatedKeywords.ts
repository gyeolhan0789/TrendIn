import { useQuery } from '@tanstack/react-query';
import { getRelatedKeywords } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useRelatedKeywords(trendId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.relatedKeywords(trendId ?? ''),
    queryFn: () => getRelatedKeywords(trendId as string),
    enabled: Boolean(trendId),
  });
}
