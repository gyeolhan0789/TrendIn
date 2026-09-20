import { useMutation, useQueryClient } from '@tanstack/react-query';
import { logout } from '../api/authApi';
import { clearAuthSession, getAuthSession } from '../api/authSessionStorage';
import { showToast } from '../../../components/common/toast';

/**
 * 서버에 남은 Refresh Token을 지웁니다. 이게 지워져야 그 토큰으로 다시 재발급받는 길이 막힙니다.
 *
 * 액세스 토큰이 만료된 채로 로그아웃하면 이 요청이 401을 받고, 인터셉터가 재발급을 걸어 다시
 * 보냅니다. 그 사이 서버는 Refresh Token을 회전시키므로, 우리가 실어 보낸 토큰은 서버가 쥔
 * 것과 달라져 지울 것을 못 찾습니다. 그러면 회전된 토큰만 14일을 더 살아남습니다.
 * 그래서 갈아 끼워진 토큰으로 한 번 더 부릅니다.
 */
async function endServerSession(refreshToken: string) {
  try {
    await logout(refreshToken);
    return;
  } catch {
    // 아래에서 한 번 더 시도합니다.
  }

  const renewed = getAuthSession();
  if (!renewed || renewed.refreshToken === refreshToken) return;
  await logout(renewed.refreshToken).catch(() => undefined);
}

export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const session = getAuthSession();
      // 서버 호출이 실패해도(리프레시 토큰까지 만료된 경우 등) 이 기기에서는 반드시 로그아웃합니다.
      if (session) await endServerSession(session.refreshToken);
      clearAuthSession();
    },
    onSuccess: () => {
      queryClient.clear();
      showToast({ message: '로그아웃했습니다.', type: 'success' });
    },
  });
}
