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
     * 소셜 로그인. 인가 화면으로 보내는 일은 화면이 하고(oauthAuthorize), 여기로는 제공자가
     * 돌려준 code 를 넘깁니다. 지금 서버가 아는 provider 는 gitlab 하나입니다.
     */
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
    // 나라별 언급량과 순위. period 는 24H·7D 만 받습니다.
    regions: (trendId: number) => `/trends/${trendId}/regions`,
    // 나라별 최초 감지일 순서. 기간을 받지 않고 늘 30일을 봅니다.
    regionJourney: (trendId: number) => `/trends/${trendId}/regions/journey`,
    /*
     * 한 나라의 날짜별 언급량도 있습니다(/regions/{countryCode}/history). 나라마다 한 번씩
     * 불러야 해서 아직 쓰지 않습니다. 나라별 증감을 보여 주기로 하면 그때 붙입니다.
     */
  },
  /*
   * 나라를 축으로 보는 조회입니다. 트렌드를 고르기 전에도 불러야 해서 /trends 아래가 아닙니다.
   * 두 조회 모두 domain 과 period 가 필수입니다.
   */
  regions: {
    // 한 분야를 나라별로 갈라 본 언급량. 지도를 칠하는 값이자 나라 목록입니다.
    list: '/regions',
    // 나라 하나에서 많이 언급된 트렌드. size 로 잘라 받습니다.
    trends: (countryCode: string) => `/regions/${countryCode}/trends`,
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
    notificationSettings: '/members/me/notification-settings',
    unreadNotificationCount: '/members/me/notifications/unread-count',
    notification: (notificationId: number) => `/members/me/notifications/${notificationId}`,
    readAllNotifications: '/members/me/notifications/read-all',
  },
} as const;
