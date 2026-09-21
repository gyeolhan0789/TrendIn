export const queryKeys = {
  auth: {
    emailCheck: (email: string) => ['auth', 'emailCheck', email] as const,
  },
  onboarding: {
    domains: ['onboarding', 'domains'] as const,
    myDomains: ['onboarding', 'myDomains'] as const,
  },
  trends: {
    // 분야·갈래·기간이 다르면 다른 목록이라 조회 조건을 그대로 키에 싣습니다.
    list: (params?: object) => ['trends', 'list', params] as const,
    // 지표와 그래프는 기간마다 달라 기간까지 키에 넣습니다.
    detail: (trendId: number, period: string) => ['trends', 'detail', trendId, period] as const,
    history: (trendId: number, period: string) => ['trends', 'history', trendId, period] as const,
    contents: (trendId: number) => ['trends', 'contents', trendId] as const,
    relatedKeywords: (trendId: number) => ['trends', 'relatedKeywords', trendId] as const,
    // 나라별 순위는 기간마다 달라 기간까지 키에 넣습니다. 확산 경로는 늘 30일이라 넣지 않습니다.
    regions: (trendId: number, period: string) => ['trends', 'regions', trendId, period] as const,
    regionJourney: (trendId: number) => ['trends', 'regionJourney', trendId] as const,
  },
  keywords: {
    search: (query: string) => ['keywords', 'search', query] as const,
  },
  notifications: {
    list: ['notifications', 'list'] as const,
    unreadCount: ['notifications', 'unreadCount'] as const,
    settings: ['notifications', 'settings'] as const,
  },
  savedTrends: {
    all: ['savedTrends'] as const,
  },
  myPage: {
    profile: ['myPage', 'profile'] as const,
    interestKeywords: ['myPage', 'interestKeywords'] as const,
    recommendedKeywords: ['myPage', 'recommendedKeywords'] as const,
  },
};
