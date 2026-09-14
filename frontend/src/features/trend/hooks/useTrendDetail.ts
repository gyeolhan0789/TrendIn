import { useQuery } from '@tanstack/react-query';
import { getTrendDetail } from '../api/trendApi';
import type { PeriodCode } from '../../../constants/filterCodes';
import { queryKeys } from '../../../utils/queryKeys';

/** 지표는 기간마다 다르므로 기간이 바뀌면 다시 받습니다. */
export function useTrendDetail(trendId: number | undefined, period: PeriodCode) {
  return useQuery({
    queryKey: queryKeys.trends.detail(trendId ?? 0, period),
    queryFn: () => getTrendDetail(trendId as number, period),
    enabled: Boolean(trendId),
  });
}
