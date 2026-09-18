import { useQuery } from '@tanstack/react-query';
import { getTrendRegions } from '../api/globalTrendApi';
import type { RegionPeriodCode } from '../../../constants/filterCodes';
import { queryKeys } from '../../../utils/queryKeys';

/** 나라별 언급량과 순위. 기간마다 달라지므로 기간이 바뀌면 다시 받습니다. */
export function useTrendRegions(trendId: number | undefined, period: RegionPeriodCode) {
  return useQuery({
    queryKey: queryKeys.trends.regions(trendId ?? 0, period),
    queryFn: () => getTrendRegions(trendId as number, period),
    enabled: Boolean(trendId),
  });
}
