import { apiClient } from '../../../api/client';
import { API_ENDPOINTS, hasEndpoint, requireEndpoint } from '../../../constants/apiEndpoints';
import { getMockAllTrends } from '../../trend/api/trendMockData';
import type { Trend } from '../../trend/types/trend';
import type { MyProfile } from '../types/myPage';

// Fictional UI fixture, matching the design mock. Replaced by the profile endpoint once it exists.
const mockProfile: MyProfile = { name: '정민수', email: 'jungms@company.co.kr', initial: 'J' };

export async function getMyProfile(): Promise<MyProfile> {
  if (!hasEndpoint(API_ENDPOINTS.myPage.profile)) return mockProfile;
  const { data } = await apiClient.get<MyProfile>(requireEndpoint(API_ENDPOINTS.myPage.profile, 'getMyProfile'));
  return data;
}

/**
 * 검색창과 추천 카드가 함께 쓰는 키워드 후보 목록입니다.
 * 두 곳이 같은 목록을 봐야 이미 등록한 키워드를 중복으로 권하지 않습니다.
 */
export async function getKeywordCatalog(): Promise<Trend[]> {
  if (!hasEndpoint(API_ENDPOINTS.myPage.keywordCatalog)) return getMockAllTrends();
  const { data } = await apiClient.get<Trend[]>(requireEndpoint(API_ENDPOINTS.myPage.keywordCatalog, 'getKeywordCatalog'));
  return data;
}
