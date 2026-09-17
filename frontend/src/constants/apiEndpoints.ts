/**
 * 백엔드 REST 경로입니다. 응답은 모두 공통 봉투(BaseResponse)에 담겨 오므로,
 * 값을 꺼내는 일은 api/apiResponse.ts 의 unwrap 이 맡습니다.
 *
 * 식별자는 서버가 Long 이라 number 로 받습니다. 문자열을 그대로 끼워 넣지 않도록 함수로 둡니다.
 */
export const API_ENDPOINTS = {
  auth: {
    signUp: '/auth/signup',
    login: '/auth/login',
    logout: '/auth/logout',
    reissue: '/auth/reissue',
    emailCheck: '/auth/email-check',
    /*
     * 비밀번호 재설정. 메일로 인증번호를 받는 단계와 실제로 바꾸는 단계로 나뉩니다.
     * 소셜 로그인과 마찬가지로 백엔드에는 아직 없고, 화면이 부를 경로만 먼저 정해 둡니다.
     */
    passwordResetCode: '/auth/password-reset/code',
    passwordReset: '/auth/password-reset',

    // 소셜 로그인은 백엔드에 아직 없습니다. 경로만 남겨 두고 화면은 '준비 중'으로 안내합니다.
    oauthLogin: (provider: string) => `/auth/oauth/${encodeURIComponent(provider)}/login`,
  },
  // 고를 수 있는 관심 분야 목록. 로그인 없이 부를 수 있는 유일한 조회 API 입니다.
  domains: '/domains',
  keywords: {
    search: '/keywords/search',
  },
  trends: {
    // domain, type, period 가 모두 필수입니다. 목록은 유형별로 따로 부릅니다.
    list: '/trends',
    detail: (trendId: number) => `/trends/${trendId}`,
    history: (trendId: number) => `/trends/${trendId}/history`,
    contents: (trendId: number) => `/trends/${trendId}/contents`,
    relatedKeywords: (trendId: number) => `/trends/${trendId}/related-keywords`,
  },
  members: {
    me: '/members/me',
    domains: '/members/me/domains',
    interestKeywords: '/members/me/interest-keywords',
    // 삭제는 키워드가 아니라 등록 식별자로 합니다.
    interestKeyword: (interestKeywordId: number) => `/members/me/interest-keywords/${interestKeywordId}`,
    recommendedKeywords: '/members/me/recommended-keywords',
    savedTrends: '/members/me/saved-trends',
    // 저장 해제도 trendId 가 아니라 savedTrendId 로 합니다.
    savedTrend: (savedTrendId: number) => `/members/me/saved-trends/${savedTrendId}`,
    notifications: '/members/me/notifications',
    unreadNotificationCount: '/members/me/notifications/unread-count',
    notification: (notificationId: number) => `/members/me/notifications/${notificationId}`,
    readAllNotifications: '/members/me/notifications/read-all',
  },
} as const;
