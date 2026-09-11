/**
 * 백엔드 API 계약이 확정되면 아래 TODO 값을 실제 endpoint로 교체합니다.
 * 임의의 경로를 확정하지 않기 위해 현재는 미설정 상태입니다.
 */
const TODO_ENDPOINT = undefined;

export const API_ENDPOINTS = {
  // 인증 API는 계약이 확정되어 경로를 그대로 적습니다.
  auth: {
    login: '/auth/login',
    logout: '/auth/logout',
    reissue: '/auth/reissue',
    oauthLogin: (provider: string) => `/auth/oauth/${encodeURIComponent(provider)}/login`,
  },
  trends: {
    top: TODO_ENDPOINT,
    new: TODO_ENDPOINT,
    resurging: TODO_ENDPOINT,
    related: TODO_ENDPOINT,
    detail: TODO_ENDPOINT,
    analysis: TODO_ENDPOINT,
    relatedKeywords: TODO_ENDPOINT,
    relatedContents: TODO_ENDPOINT,
  },
  savedTrends: {
    list: TODO_ENDPOINT,
    save: TODO_ENDPOINT,
    delete: TODO_ENDPOINT,
  },
  // 등록한 관심 키워드 자체는 저장 보드처럼 기기에만 두므로 endpoint가 없습니다.
  myPage: {
    profile: TODO_ENDPOINT,
    keywordCatalog: TODO_ENDPOINT,
  },
} as const;

export function hasEndpoint(endpoint: string | undefined): endpoint is string {
  return Boolean(endpoint);
}

export function requireEndpoint(endpoint: string | undefined, apiName: string): string {
  if (!endpoint) {
    throw new Error(`${apiName} endpoint is not configured yet.`);
  }

  return endpoint;
}
