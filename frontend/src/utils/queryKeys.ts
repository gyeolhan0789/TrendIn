export const queryKeys = {
  auth: {
    emailCheck: (email: string) => ['auth', 'emailCheck', email] as const,
  },
  trends: {
    top: (params?: object) => ['trends', 'top', params] as const,
    new: (params?: object) => ['trends', 'new', params] as const,
    resurging: (params?: object) => ['trends', 'resurging', params] as const,
    related: (params?: object) => ['trends', 'related', params] as const,
    detail: (trendId: string) => ['trends', 'detail', trendId] as const,
    analysis: (trendId: string) => ['trends', 'analysis', trendId] as const,
    relatedKeywords: (trendId: string) => ['trends', 'relatedKeywords', trendId] as const,
    relatedContents: (trendId: string) => ['trends', 'relatedContents', trendId] as const,
  },
  savedTrends: {
    all: ['savedTrends'] as const,
  },
  myPage: {
    profile: ['myPage', 'profile'] as const,
    keywordCatalog: ['myPage', 'keywordCatalog'] as const,
  },
};
