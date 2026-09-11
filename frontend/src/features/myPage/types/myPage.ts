import type { Trend } from '../../trend/types/trend';

/** 키워드마다 켜고 끄는 알림 두 가지. 키워드 메뉴의 토글과 1:1로 대응합니다. */
export interface KeywordAlerts {
  trend: boolean;
  weekly: boolean;
}

/** 사용자가 등록한 관심 키워드. 저장 보드와 마찬가지로 기기에만 보관합니다. */
export interface InterestKeyword {
  keywordId: string;
  keyword: string;
  /** 트렌드 목록에서 고른 키워드만 값이 있습니다. 직접 입력한 키워드는 아직 추이가 없습니다. */
  trendId?: string;
  alerts: KeywordAlerts;
}

export interface InterestKeywordState {
  /** 배열 순서가 곧 화면 순서입니다. 끌어 옮기거나 메뉴로 위아래로 옮깁니다. */
  keywords: InterestKeyword[];
}

/** 화면에 그릴 관심 키워드 한 줄. 등록 정보에 트렌드 지표를 붙인 것입니다. */
export interface InterestKeywordView extends InterestKeyword {
  /** 직접 입력한 키워드이거나 트렌드 목록에서 사라졌으면 없습니다. */
  trend?: Trend;
  category?: string;
  alertCount: number;
}

export interface MyProfile {
  name: string;
  email: string;
  /** 헤더 아바타와 같은 글자를 써야 해서 파생하지 않고 값으로 받습니다. */
  initial: string;
}

/** 추천 키워드 카드 한 장. */
export interface RecommendedKeyword {
  trendId: string;
  keyword: string;
  /** 왜 추천했는지 한 줄. 카드 아래에 그대로 보여줍니다. */
  reason: string;
}
