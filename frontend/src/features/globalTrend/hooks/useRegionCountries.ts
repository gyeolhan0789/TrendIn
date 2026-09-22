import { useQuery } from '@tanstack/react-query';
import { getRegionCountries } from '../api/globalTrendApi';
import type { RegionPeriodCode } from '../../../constants/filterCodes';
import { queryKeys } from '../../../utils/queryKeys';

/** 분야 하나의 나라별 언급량. 지도를 칠하는 값이자 왼쪽 나라 목록입니다. */
export function useRegionCountries(domain: string | undefined, period: RegionPeriodCode) {
  return useQuery({
    queryKey: queryKeys.regions.countries(domain ?? '', period),
    queryFn: () => getRegionCountries(domain as string, period),
    enabled: Boolean(domain),
  });
}
