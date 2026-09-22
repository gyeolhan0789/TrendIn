import { useQuery } from '@tanstack/react-query';
import { getCountryTrends } from '../api/globalTrendApi';
import type { RegionPeriodCode } from '../../../constants/filterCodes';
import { queryKeys } from '../../../utils/queryKeys';

/** 나라 하나에서 많이 언급된 트렌드. 나라를 고르기 전에는 부르지 않습니다. */
export function useCountryTrends(
  domain: string | undefined,
  countryCode: string | undefined,
  period: RegionPeriodCode,
  size: number,
) {
  return useQuery({
    queryKey: queryKeys.regions.countryTrends(domain ?? '', countryCode ?? '', period, size),
    queryFn: () => getCountryTrends(domain as string, countryCode as string, period, size),
    enabled: Boolean(domain) && Boolean(countryCode),
  });
}
