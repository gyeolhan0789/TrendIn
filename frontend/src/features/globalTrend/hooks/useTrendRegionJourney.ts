import { useQuery } from '@tanstack/react-query';
import { getTrendRegionJourney } from '../api/globalTrendApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 트렌드가 퍼져 나간 순서. 기간을 받지 않아 기간을 바꿔도 다시 받지 않습니다.
 * 30일 안에 언급이 한 번이라도 잡힌 나라만 들어오므로, 최근 순위보다 나라가 많을 수 있습니다.
 */
export function useTrendRegionJourney(trendId: number | undefined) {
  return useQuery({
    queryKey: queryKeys.trends.regionJourney(trendId ?? 0),
    queryFn: () => getTrendRegionJourney(trendId as number),
    enabled: Boolean(trendId),
  });
}
