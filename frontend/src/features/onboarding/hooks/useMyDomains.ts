import { useQuery } from '@tanstack/react-query';
import { getMyDomains } from '../api/onboardingApi';
import { queryKeys } from '../../../utils/queryKeys';

/** 내가 고른 분야. 다시 들어왔을 때 고른 것을 그대로 켜 두려고 씁니다. */
export function useMyDomains(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.onboarding.myDomains,
    queryFn: getMyDomains,
    enabled,
  });
}
