import { useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteSavedTrend, saveTrend } from '../api/savedTrendApi';
import { useSavedTrends } from './useSavedTrends';
import { getApiErrorMessage } from '../../../api/apiResponse';
import { showToast } from '../../../components/common/toast';
import { queryKeys } from '../../../utils/queryKeys';

interface ToggleTarget {
  trendId: number;
  keyword: string;
}

/**
 * 담기와 담기 취소를 한 손잡이로 묶습니다.
 *
 * 지우려면 트렌드가 아니라 저장 기록의 식별자가 필요해서, 저장 목록에서 짝을 찾아 씁니다.
 * 그래서 담긴 상태 표시와 취소가 같은 자료를 보게 되고 둘이 어긋나지 않습니다.
 */
export function useToggleSavedTrend() {
  const queryClient = useQueryClient();
  const savedTrendsQuery = useSavedTrends();

  const savedTrendIdByTrendId = useMemo(() => {
    const entries = savedTrendsQuery.data?.trends.map((trend) => [trend.trendId, trend.savedTrendId] as const) ?? [];
    return new Map(entries);
  }, [savedTrendsQuery.data]);

  const mutation = useMutation({
    mutationFn: async ({ trendId }: ToggleTarget) => {
      const savedTrendId = savedTrendIdByTrendId.get(trendId);
      if (savedTrendId === undefined) {
        await saveTrend(trendId);
        return { saved: true };
      }
      await deleteSavedTrend(savedTrendId);
      return { saved: false };
    },
    onSuccess: ({ saved }, { keyword }) => {
      showToast({ message: saved ? `${keyword}을(를) 담았습니다.` : `${keyword}을(를) 담기에서 뺐습니다.`, type: 'success' });
    },
    // 이미 담았거나 이미 지운 트렌드처럼, 서버가 이유를 알려 주는 경우에는 그 문구를 그대로 보여 줍니다.
    onError: (error) => {
      showToast({ message: getApiErrorMessage(error) ?? '담기에 실패했습니다.', type: 'error' });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.savedTrends.all }),
  });

  return {
    isSaved: (trendId: number) => savedTrendIdByTrendId.has(trendId),
    isReady: savedTrendsQuery.isSuccess,
    pendingTrendId: mutation.isPending ? mutation.variables.trendId : undefined,
    toggle: (target: ToggleTarget) => mutation.mutate(target),
  };
}
