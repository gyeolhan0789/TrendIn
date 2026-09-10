import { useMutation, useQueryClient } from '@tanstack/react-query';
import { saveTrend } from '../api/savedTrendApi';
import { queryKeys } from '../../../utils/queryKeys';
import { showToast } from '../../../components/common/toast';

interface UseSaveTrendOptions {
  /** 담기 흐름은 어느 영역에 담겼는지까지 알려주므로 문구를 바꿔 끼웁니다. */
  successMessage?: (trendId: string) => string;
}

export function useSaveTrend({ successMessage }: UseSaveTrendOptions = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: saveTrend,
    onSuccess: (_savedTrend, trendId) => {
      showToast({ message: successMessage?.(trendId) ?? '트렌드를 저장했습니다.', type: 'success' });
      queryClient.invalidateQueries({ queryKey: queryKeys.savedTrends.all, refetchType: 'active' });
      queryClient.invalidateQueries({ queryKey: queryKeys.trends.detail(trendId) });
    },
    onError: () => showToast({ message: '트렌드 저장에 실패했습니다.', type: 'error' }),
  });
}
