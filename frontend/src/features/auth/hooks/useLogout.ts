import { useMutation, useQueryClient } from '@tanstack/react-query';
import { logout } from '../api/authApi';
import { clearAuthSession, getAuthSession } from '../api/authSessionStorage';
import { showToast } from '../../../components/common/toast';

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const session = getAuthSession();
      // 서버 호출이 실패해도(토큰이 이미 만료된 경우 등) 이 기기에서는 반드시 로그아웃합니다.
      if (session) await logout(session.refreshToken).catch(() => undefined);
      clearAuthSession();
    },
    onSuccess: () => {
      queryClient.clear();
      showToast({ message: '로그아웃했습니다.', type: 'success' });
    },
  });
}
