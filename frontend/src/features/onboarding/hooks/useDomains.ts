import { useQuery } from '@tanstack/react-query';
import { getDomains } from '../api/onboardingApi';
import { queryKeys } from '../../../utils/queryKeys';

/** 고를 수 있는 분야 전체. 배포 전에는 바뀌지 않아서 오래 들고 있어도 됩니다. */
export function useDomains() {
  return useQuery({
    queryKey: queryKeys.onboarding.domains,
    queryFn: getDomains,
    staleTime: 30 * 60_000,
  });
}
