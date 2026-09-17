import { apiClient } from '../../../api/client';
import type { ApiResponse } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { InterestKeyword, MyProfile, RecommendedKeyword } from '../types/myPage';

export async function getMyProfile(): Promise<MyProfile> {
  return unwrap(apiClient.get<ApiResponse<MyProfile>>(API_ENDPOINTS.members.me));
}

/**
 * 지금 서버가 고칠 수 있게 열어 둔 것은 닉네임 하나입니다. 응답으로 고쳐진 프로필이 통째로 옵니다.
 */
export async function updateMyProfile(nickname: string): Promise<MyProfile> {
  return unwrap(apiClient.patch<ApiResponse<MyProfile>>(API_ENDPOINTS.members.me, { nickname }));
}

/** 분야를 주면 그 분야의 키워드만, 주지 않으면 전부 등록한 순서대로 옵니다. */
export async function getInterestKeywords(domain?: string): Promise<InterestKeyword[]> {
  return unwrap(apiClient.get<ApiResponse<InterestKeyword[]>>(API_ENDPOINTS.members.interestKeywords, {
    params: domain ? { domain } : undefined,
  }));
}

/** 등록은 이름이 아니라 키워드 식별자로 합니다. 서버에 없는 말은 등록할 수 없습니다. */
export async function registerInterestKeyword(keywordId: number): Promise<void> {
  await apiClient.post<ApiResponse<unknown>>(API_ENDPOINTS.members.interestKeywords, { keywordId });
}

export async function deleteInterestKeyword(interestKeywordId: number): Promise<void> {
  await apiClient.delete<ApiResponse<null>>(API_ENDPOINTS.members.interestKeyword(interestKeywordId));
}

/**
 * 관심 키워드와 함께 언급되는 키워드를 권합니다.
 * 관심 키워드를 하나도 등록하지 않았으면 기댈 곳이 없어 빈 목록이 옵니다.
 */
export async function getRecommendedKeywords(): Promise<RecommendedKeyword[]> {
  return unwrap(apiClient.get<ApiResponse<RecommendedKeyword[]>>(API_ENDPOINTS.members.recommendedKeywords));
}
