import { useQuery } from '@tanstack/react-query';
import { searchKeywords } from '../api/keywordApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 검색어가 비어 있으면 부르지 않습니다. 글자를 칠 때마다 보내지 않도록,
 * 화면에서 잠시 멈춘 뒤의 값만 넘겨 줍니다.
 */
export function useKeywordSearch(query: string) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: queryKeys.keywords.search(trimmed),
    queryFn: () => searchKeywords(trimmed),
    enabled: trimmed.length > 0,
    // 같은 말을 다시 치는 경우가 잦아 결과를 잠시 들고 있습니다.
    staleTime: 60_000,
  });
}
