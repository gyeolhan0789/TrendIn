import { useMutation } from '@tanstack/react-query';
import { requestPasswordResetCode, resetPassword } from '../api/authApi';
import { normalizeEmail } from '../validation';
import type { PasswordResetRequest } from '../types/auth';

/**
 * 비밀번호를 잊은 사람에게 인증번호를 보냅니다.
 *
 * 로그인·가입과 달리 세션을 만들지 않으므로 캐시도 건드리지 않습니다. 이 화면을 지나는 동안
 * 로그인 상태는 바뀌지 않습니다.
 */
export function useRequestPasswordResetCode() {
  return useMutation<void, unknown, string>({
    // 가입할 때 소문자로 눕혀 저장했으니, 인증번호를 보낼 주소도 같은 모양으로 맞춥니다.
    mutationFn: (email) => requestPasswordResetCode({ email: normalizeEmail(email) }),
  });
}

/** 인증번호와 새 비밀번호를 함께 보냅니다. 성공해도 로그인은 되지 않아, 화면이 로그인으로 보냅니다. */
export function useResetPassword() {
  return useMutation<void, unknown, PasswordResetRequest>({
    mutationFn: ({ email, code, password }) =>
      resetPassword({ email: normalizeEmail(email), code: code.trim(), password }),
  });
}
