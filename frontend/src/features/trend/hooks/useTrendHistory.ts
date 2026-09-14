import { useQuery } from '@tanstack/react-query';
import { getTrendHistory } from '../api/trendApi';
import type { PeriodCode } from '../../../constants/filterCodes';
import { queryKeys } from '../../../utils/queryKeys';

export function useTrendHistory(trendId: number | undefined, period: PeriodCode) {
  return useQuery({
    queryKey: queryKeys.trends.history(trendId ?? 0, period),
    queryFn: () => getTrendHistory(trendId as number, period),
    enabled: Boolean(trendId),
  });
}
