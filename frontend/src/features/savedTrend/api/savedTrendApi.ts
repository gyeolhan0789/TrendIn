import { apiClient } from '../../../api/client';
import type { ApiResponse, Page } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import { SAVED_TREND_PERIOD } from '../../../constants/filterCodes';
import type { SavedTrend, SavedTrendList } from '../types/savedTrend';

/**
 * 한 번에 다 받아 화면과 담기 표시가 같은 목록을 보게 합니다.
 * 저장한 개수가 이보다 많으면 뒤쪽은 받지 못하므로, 더 있는지를 함께 알려 화면에서 밝힙니다.
 */
const MAX_SAVED_TRENDS = 200;

export async function getSavedTrends(): Promise<SavedTrendList> {
  const data = await unwrap(apiClient.get<ApiResponse<Page<SavedTrend>>>(API_ENDPOINTS.members.savedTrends, {
    // 지표는 기간마다 달라지는데 이 화면에는 기간을 고르는 자리가 없어 기본 기간으로 받습니다.
    params: { period: SAVED_TREND_PERIOD, page: 0, size: MAX_SAVED_TRENDS },
  }));
  return { trends: data.content, hasNext: data.hasNext };
}

export async function saveTrend(trendId: number): Promise<void> {
  await apiClient.post<ApiResponse<unknown>>(API_ENDPOINTS.members.savedTrends, { trendId });
}

/** 지우는 키는 트렌드가 아니라 저장 기록입니다. */
export async function deleteSavedTrend(savedTrendId: number): Promise<void> {
  await apiClient.delete<ApiResponse<null>>(API_ENDPOINTS.members.savedTrend(savedTrendId));
}
