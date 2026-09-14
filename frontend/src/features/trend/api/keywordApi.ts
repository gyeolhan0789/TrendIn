import { apiClient } from '../../../api/client';
import type { ApiResponse, Page } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { KeywordSearchItem, KeywordSearchResult } from '../types/keyword';

/**
 * 이름의 일부로 키워드를 찾습니다. 서버가 앞뒤 공백과 대소문자를 정리해 비교하므로 그대로 보냅니다.
 * 트렌드에 오르지 않은 키워드도 나오며, 그때는 트렌드 식별자와 증가율이 비어 옵니다.
 */
export async function searchKeywords(query: string, page = 0, size = 10): Promise<KeywordSearchResult> {
  const data = await unwrap(apiClient.get<ApiResponse<Page<KeywordSearchItem>>>(API_ENDPOINTS.keywords.search, {
    params: { query, page, size },
  }));
  return { items: data.content, hasNext: data.hasNext };
}
