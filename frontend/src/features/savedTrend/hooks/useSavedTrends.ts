import { useQuery } from '@tanstack/react-query';
import { getSavedTrends } from '../api/savedTrendApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 저장한 트렌드 전부. 저장 화면과 담기 버튼이 같은 캐시를 보므로,
 * 어느 화면에서 담고 빼도 다른 화면이 곧바로 따라옵니다.
 */
export function useSavedTrends() {
  return useQuery({ queryKey: queryKeys.savedTrends.all, queryFn: getSavedTrends });
}
