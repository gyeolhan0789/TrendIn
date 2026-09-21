import { useMutation, useQueryClient } from '@tanstack/react-query';
import { login, signUp } from '../api/authApi';
import { startAuthSession } from '../api/authSessionStorage';
import { normalizeEmail } from '../validation';
import type { LoginResult, SignUpRequest, SignUpResult } from '../types/auth';

interface SignUpOutcome {
  member: SignUpResult;
  /**
   * 가입 응답에는 토큰이 없어서 곧바로 로그인까지 이어 붙입니다.
   * 그 로그인만 실패하면 계정은 이미 만들어진 뒤이므로, 가입 실패로 되돌리지 않고
   * 세션 없이 돌려보내 로그인 화면에서 다시 시도하게 합니다.
   */
  session?: LoginResult;
}

export function useSignUp() {
  const queryClient = useQueryClient();

  return useMutation<SignUpOutcome, unknown, SignUpRequest>({
    mutationFn: async ({ email, password, nickname }) => {
      const normalized = normalizeEmail(email);
      const member = await signUp({ email: normalized, password, nickname: nickname.trim() });

      try {
        const session = await login({ email: normalized, password });
        startAuthSession({
          accessToken: session.accessToken,
          refreshToken: session.refreshToken,
          tokenType: session.tokenType,
          email: normalized,
          onboardingCompleted: session.onboardingCompleted,
        });
        return { member, session };
      } catch {
        return { member };
      }
    },
    onSuccess: () => queryClient.clear(),
  });
}
