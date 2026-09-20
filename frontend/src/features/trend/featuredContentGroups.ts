import type { TrendType } from './types/trend';

/** 홈 콘텐츠와 트렌드 탐색이 따르는 서버 갈래 순서입니다. */
export const FEATURED_CONTENT_GROUPS: readonly { type: TrendType; label: string }[] = [
  { type: 'CURRENT', label: '인기' },
  { type: 'NEW', label: '신규' },
  { type: 'RISING', label: '급상승' },
];
