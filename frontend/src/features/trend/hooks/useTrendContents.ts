import { useInfiniteQuery } from '@tanstack/react-query';
import { getTrendContents } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

const PAGE_SIZE = 10;

/**
 * 원본 소스는 한 번에 다 받지 않고 더 보기로 이어 받습니다.
 * 서버가 전체 개수를 주지 않아 다음 쪽이 있는지는 hasNext 로만 알 수 있습니다.
 */
export function useTrendContents(trendId: number | undefined) {
  return useInfiniteQuery({
    queryKey: queryKeys.trends.contents(trendId ?? 0),
    queryFn: ({ pageParam }) => getTrendContents(trendId as number, pageParam, PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => (lastPage.hasNext ? lastPage.page + 1 : undefined),
    enabled: Boolean(trendId),
  });
}
