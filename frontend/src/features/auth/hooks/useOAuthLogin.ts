import { useMutation, useQueryClient } from '@tanstack/react-query';
import { oauthLogin } from '../api/authApi';
import { startAuthSession } from '../api/authSessionStorage';
import type { OAuthLoginRequest, OAuthLoginResult } from '../types/auth';

interface OAuthLoginVariables extends OAuthLoginRequest {
  provider: string;
}

/**
 * 제공자 콜백이 넘겨준 code·state로 로그인을 마칩니다.
 * 지원 제공자는 아직 확정되지 않아 provider를 값으로 받습니다.
 */
export function useOAuthLogin() {
  const queryClient = useQueryClient();

  return useMutation<OAuthLoginResult, unknown, OAuthLoginVariables>({
    mutationFn: async ({ provider, code, state }) => {
      const result = await oauthLogin(provider, { code, state });
      startAuthSession({
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        tokenType: result.tokenType,
        // OAuth 응답에는 이메일이 없습니다. 회원 정보 조회가 붙으면 그때 채웁니다.
        email: '',
        onboardingCompleted: result.onboardingCompleted,
      });
      return result;
    },
    onSuccess: () => queryClient.clear(),
  });
}
