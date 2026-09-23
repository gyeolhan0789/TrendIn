import { useMutation, useQueryClient } from '@tanstack/react-query';
import { withdraw } from '../api/myPageApi';
import { clearAuthSession } from '../../auth/api/authSessionStorage';
import { getApiErrorMessage } from '../../../api/apiResponse';
import { showToast } from '../../../components/common/toast';

/**
 * 계정을 탈퇴 처리하고 이 기기의 세션을 지웁니다.
 *
 * **로그아웃과 달리 서버에 리프레시 토큰을 보내지 않습니다.** 서버가 탈퇴 처리하면서 회원의
 * 세션을 통째로 지우므로, 여기서 할 일은 이 기기에 남은 값을 치우는 것뿐입니다.
 *
 * ⚠️ **액세스 토큰은 서버에서 즉시 폐기되지 않습니다.** 서명과 만료만 보는 JWT라 남은 유효
 * 기간 동안 필터를 통과하고, 그 요청은 회원을 찾지 못해 404로 끝납니다. 그러니 탈퇴한
 * 기기에 토큰을 남겨 두면 안 됩니다.
 */
export function useWithdraw() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: withdraw,
    onSuccess: () => {
      /*
       * 성공했을 때만 세션을 버립니다. 실패했는데 버리면 계정은 남아 있는데 로그아웃만 된
       * 상태가 되어, 사용자는 탈퇴됐는지 아닌지 알 수 없게 됩니다.
       *
       * 캐시를 비우는 것도 여기서 합니다. 남겨 두면 다음 사람이 이 기기에서 로그인했을 때
       * 앞 사람의 관심 키워드나 알림이 잠깐 비칩니다.
       *
       * **성공은 알리지 않습니다.** 부르는 쪽이 곧바로 랜딩으로 보내므로, 알림이 뜬다면
       * 이미 떠난 화면의 일을 새 화면 위에서 말하는 셈입니다. 로그인해 있지 않다는 것이
       * 그 자리에서 이미 보입니다.
       */
      clearAuthSession();
      queryClient.clear();
    },
    onError: (error) => showToast({
      message: getApiErrorMessage(error) ?? '계정을 삭제하지 못했습니다.',
      type: 'error',
    }),
  });
}
