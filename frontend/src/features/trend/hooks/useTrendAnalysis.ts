import { useQuery } from '@tanstack/react-query';
import { getTrendAnalysis } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useTrendAnalysis(trendId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.analysis(trendId ?? ''),
    queryFn: () => getTrendAnalysis(trendId as string),
    enabled: Boolean(trendId),
  });
}
