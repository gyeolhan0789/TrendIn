import { useQuery } from '@tanstack/react-query';
import { getKeywordCatalog } from '../api/myPageApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useKeywordCatalog() {
  return useQuery({ queryKey: queryKeys.myPage.keywordCatalog, queryFn: getKeywordCatalog });
}
