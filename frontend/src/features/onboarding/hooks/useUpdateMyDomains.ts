import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateMyDomains } from '../api/onboardingApi';
import { markOnboardingCompleted } from '../../auth/api/authSessionStorage';
import { queryKeys } from '../../../utils/queryKeys';
import type { DomainOption } from '../types/onboarding';

export function useUpdateMyDomains() {
  const queryClient = useQueryClient();

  return useMutation<DomainOption[], unknown, string[]>({
    mutationFn: updateMyDomains,
    onSuccess: (domains) => {
      markOnboardingCompleted();
      queryClient.setQueryData(queryKeys.onboarding.myDomains, domains);
      // 분야에서 빠진 관심 키워드는 서버가 함께 지우므로, 키워드 목록도 다시 받아야 합니다.
      queryClient.invalidateQueries({ queryKey: queryKeys.myPage.keywordCatalog });
    },
  });
}
