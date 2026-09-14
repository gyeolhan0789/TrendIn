import { useQuery } from '@tanstack/react-query';
import { getTrendRelatedKeywords } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

/** 서버에서 연관 키워드를 받아옵니다. 기준이 될 트렌드가 없으면 부르지 않습니다. */
export function useTrendRelatedKeywords(trendId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.relatedKeywords(trendId ?? 0),
    queryFn: () => getTrendRelatedKeywords(trendId as number),
    enabled: Boolean(trendId),
  });
}
