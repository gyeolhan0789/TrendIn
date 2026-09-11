import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { DomainOption } from '../types/onboarding';

/** 고를 수 있는 분야 전체. 로그인 없이도 볼 수 있습니다. */
export async function getDomains(): Promise<DomainOption[]> {
  const { data } = await apiClient.get<ApiResponse<DomainOption[]>>(API_ENDPOINTS.domains);
  return data.data;
}

/** 내가 고른 분야. 아직 고르지 않았으면 빈 배열입니다. */
export async function getMyDomains(): Promise<DomainOption[]> {
  const { data } = await apiClient.get<ApiResponse<DomainOption[]>>(API_ENDPOINTS.members.domains);
  return data.data;
}

/**
 * 고른 분야로 통째로 교체합니다. 최초로 성공하면 서버가 온보딩을 완료 처리합니다.
 * 빠진 분야에 속한 관심 키워드도 같은 요청에서 지워지므로, 고쳐 고를 때는 그 점을 알려야 합니다.
 */
export async function updateMyDomains(domains: string[]): Promise<DomainOption[]> {
  const { data } = await apiClient.put<ApiResponse<DomainOption[]>>(
    API_ENDPOINTS.members.domains,
    { domains },
  );
  return data.data;
}
