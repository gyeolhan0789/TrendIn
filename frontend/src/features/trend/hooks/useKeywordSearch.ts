import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { searchKeywords } from '../api/keywordApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 검색어가 비어 있으면 부르지 않습니다. 글자를 칠 때마다 보내지 않도록,
 * 화면에서 잠시 멈춘 뒤의 값만 넘겨 줍니다.
 *
 * 이 API는 토큰을 요구합니다. 로그인 전에도 열리는 화면은 enabled 를 내려 아예 묻지 않습니다.
 */
export function useKeywordSearch(query: string, enabled = true) {
  const trimmed = query.trim();
  return useQuery({
    queryKey: queryKeys.keywords.search(trimmed),
    queryFn: () => searchKeywords(trimmed),
    enabled: enabled && trimmed.length > 0,
    // 같은 말을 다시 치는 경우가 잦아 결과를 잠시 들고 있습니다.
    staleTime: 60_000,
  });
}

const SEARCH_PAGE_SIZE = 10;

/** 홈 검색 결과는 첫 10개부터 시작해 더보기를 누를 때 다음 10개를 이어 붙입니다. */
export function useInfiniteKeywordSearch(query: string, enabled = true) {
  const trimmed = query.trim();
  return useInfiniteQuery({
    queryKey: [...queryKeys.keywords.search(trimmed), 'pages'],
    queryFn: ({ pageParam }) => searchKeywords(trimmed, pageParam, SEARCH_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (lastPage.hasNext ? pages.length : undefined),
    enabled: enabled && trimmed.length > 0,
    staleTime: 60_000,
  });
}
