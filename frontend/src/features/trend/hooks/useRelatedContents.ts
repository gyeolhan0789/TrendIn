import { useQuery } from '@tanstack/react-query';
import { getRelatedContents } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useRelatedContents(trendId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.relatedContents(trendId ?? ''),
    queryFn: () => getRelatedContents(trendId as string),
    enabled: Boolean(trendId),
  });
}
