import { useQuery } from '@tanstack/react-query';
import { checkEmailAvailable } from '../api/authApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 가입 화면에서 이메일 칸을 떠날 때 한 번 확인합니다.
 * 같은 이메일을 다시 확인하지 않도록 결과를 이메일별로 캐시합니다.
 */
export function useEmailAvailability(email: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.auth.emailCheck(email),
    queryFn: () => checkEmailAvailable(email),
    enabled: enabled && Boolean(email),
    retry: false,
    staleTime: 30_000,
  });
}
