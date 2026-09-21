import { useMutation, useQueryClient } from '@tanstack/react-query';
import { login } from '../api/authApi';
import { startAuthSession } from '../api/authSessionStorage';
import { normalizeEmail } from '../validation';
import type { LoginRequest, LoginResult } from '../types/auth';

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation<LoginResult, unknown, LoginRequest>({
    mutationFn: async ({ email, password }) => {
      const normalized = normalizeEmail(email);
      const result = await login({ email: normalized, password });
      startAuthSession({
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        tokenType: result.tokenType,
        email: normalized,
        onboardingCompleted: result.onboardingCompleted,
      });
      return result;
    },
    // 앞서 보던 자료는 다른 계정의 것일 수 있어, 로그인 시점에 캐시를 비웁니다.
    onSuccess: () => queryClient.clear(),
  });
}
