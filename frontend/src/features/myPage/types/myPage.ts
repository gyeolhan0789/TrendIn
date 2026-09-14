import type { TrendDomainRef } from '../../trend/types/trend';

/**
 * 등록한 관심 키워드입니다.
 * 지우는 키는 키워드가 아니라 등록 기록(interestKeywordId)입니다.
 * 분야는 서버가 코드만 주므로 표시 이름은 분야 목록에서 찾아 씁니다.
 */
export interface InterestKeyword {
  interestKeywordId: number;
  keywordId: number;
  keyword: string;
  domain: string;
}

/** 내 관심 키워드와 함께 언급되는 키워드. 점수가 높을수록 가깝습니다. */
export interface RecommendedKeyword {
  keywordId: number;
  keyword: string;
  domain: TrendDomainRef;
  relationScore: number;
}

export interface MyProfile {
  memberId: number;
  email: string;
  nickname: string;
  onboardingCompleted: boolean;
}
