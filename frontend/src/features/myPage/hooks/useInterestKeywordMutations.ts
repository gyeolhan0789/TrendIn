import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteInterestKeyword, registerInterestKeyword } from '../api/myPageApi';
import { getApiErrorMessage } from '../../../api/apiResponse';
import { showToast } from '../../../components/common/toast';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 관심 키워드를 등록하고 뺍니다.
 * 관심 키워드가 바뀌면 추천도 달라지므로 추천 목록까지 함께 다시 받습니다.
 */
function useInvalidateInterestKeywords() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.myPage.interestKeywords });
    void queryClient.invalidateQueries({ queryKey: queryKeys.myPage.recommendedKeywords });
  };
}

export function useRegisterInterestKeyword() {
  const invalidate = useInvalidateInterestKeywords();

  return useMutation({
    mutationFn: ({ keywordId }: { keywordId: number; keyword: string }) => registerInterestKeyword(keywordId),
    /*
     * **성공은 알리지 않습니다.** 담는 자리마다 누른 것이 그 자리에서 바뀝니다 — ＋가
     * 체크로 넘어가고 꼬리표 색이 바뀝니다. 그 위에 알림까지 띄우면 같은 말을 두 번 하고,
     * 여러 개를 이어 담을 때 화면을 가립니다.
     *
     * 실패는 남깁니다. 그쪽은 자리에서 알 방법이 없습니다.
     */
    onSuccess: () => invalidate(),
    // 이미 등록한 키워드처럼 서버가 이유를 알려 주는 실패는 그 문구를 그대로 보여 줍니다.
    onError: (error, { keyword }) => showToast({
      message: getApiErrorMessage(error) ?? `${keyword}을(를) 관심 키워드에 등록하지 못했습니다.`,
      type: 'error',
    }),
  });
}

export function useDeleteInterestKeyword() {
  const invalidate = useInvalidateInterestKeywords();

  return useMutation({
    mutationFn: ({ interestKeywordId }: { interestKeywordId: number; keyword: string }) =>
      deleteInterestKeyword(interestKeywordId),
    /* 담기와 같은 이유로 성공은 알리지 않습니다. 빼는 자리에서 결과가 바로 보입니다. */
    onSuccess: () => invalidate(),
    onError: (error, { keyword }) => showToast({
      message: getApiErrorMessage(error) ?? `${keyword}을(를) 관심 키워드에서 빼지 못했습니다.`,
      type: 'error',
    }),
  });
}
