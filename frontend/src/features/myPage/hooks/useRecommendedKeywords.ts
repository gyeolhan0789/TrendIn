import { useQuery } from '@tanstack/react-query';
import { getRecommendedKeywords } from '../api/myPageApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useRecommendedKeywords() {
  return useQuery({ queryKey: queryKeys.myPage.recommendedKeywords, queryFn: getRecommendedKeywords });
}
