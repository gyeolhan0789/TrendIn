import { useInfiniteQuery } from '@tanstack/react-query';
import { getTrendContents } from '../api/trendApi';
import { queryKeys } from '../../../utils/queryKeys';

/** 한 쪽에 여덟 건. 트렌드 하나에 기사가 100건을 넘기도 해서 쪽이 너무 잘게 쪼개지지 않게 잡았습니다. */
const PAGE_SIZE = 8;

/**
 * 원본 소스를 쪽 단위로 받습니다. 받은 쪽은 쌓아 두므로 앞으로 갈 때만 서버를 부르고
 * 뒤로 갈 때는 이미 받은 것을 그대로 보여 줍니다.
 *
 * 서버가 전체 개수를 주지 않아 몇 쪽인지는 끝까지 가 보기 전에는 알 수 없습니다.
 * 다음 쪽이 있는지만 hasNext 로 압니다.
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
