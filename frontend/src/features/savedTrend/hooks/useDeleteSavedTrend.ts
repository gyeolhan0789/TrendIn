import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteSavedTrend } from '../api/savedTrendApi';
import { queryKeys } from '../../../utils/queryKeys';
import { showToast } from '../../../components/common/toast';

export function useDeleteSavedTrend() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSavedTrend,
    onSuccess: () => {
      showToast({ message: '저장한 트렌드를 삭제했습니다.', type: 'success' });
      queryClient.invalidateQueries({ queryKey: queryKeys.savedTrends.all });
    },
    onError: () => showToast({ message: '저장한 트렌드 삭제에 실패했습니다.', type: 'error' }),
  });
}
