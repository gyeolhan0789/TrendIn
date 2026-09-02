import { useMutation, useQueryClient } from '@tanstack/react-query';
import { saveTrend } from '../api/savedTrendApi';
import { queryKeys } from '../../../utils/queryKeys';
import { showToast } from '../../../components/common/toast';

export function useSaveTrend() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: saveTrend,
    onSuccess: (_savedTrend, trendId) => {
      showToast({ message: '트렌드를 저장했습니다.', type: 'success' });
      queryClient.invalidateQueries({ queryKey: queryKeys.savedTrends.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.trends.detail(trendId) });
    },
    onError: () => showToast({ message: '트렌드 저장에 실패했습니다.', type: 'error' }),
  });
}
