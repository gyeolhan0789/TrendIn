import type { RelatedKeyword, Trend, TrendAnalysis, TrendContent, TrendDetail, TrendFilterParams } from '../types/trend';

export type MockCategoryId = 'dev' | 'fashion';
type Period = 'day' | 'week' | 'month';
type Entry = [string, string, string];

export interface MockCategory {
  id: MockCategoryId;
  name: string;
  icon: string;
  summary: string;
  insight: string;
  keywords: string[];
  top: Entry[];
  fresh: Entry[];
  rising: Entry[];
}

// Copied from frontend-demo/app/trends.ts. These are fictional UI fixtures, not live findings.
export const mockCategories: MockCategory[] = [
  { id: 'dev', name: '개발', icon: '</>', summary: '질문에 답하던 AI가 이제 직접 도구를 쓰고, 일을 끝냅니다. 다음 흐름은 ‘실행’에 있습니다.', insight: '더 똑똑한 모델에서, 실제로 일하는 AI로.', keywords: ['Agentic Workflow', 'MCP', 'AI Coding', 'Multi-agent'], top: [['AI Agent', '답변하는 AI에서, 실행하는 AI로', '인공지능'], ['Vibe Coding', '코드보다 의도가 먼저인 개발', '개발 문화'], ['MCP', 'AI와 도구를 연결하는 새로운 표준', 'AI 인프라'], ['Local LLM', '내 기기에서 직접 실행하는 언어 모델', '오픈소스'], ['Rust', '더 안전하고 빠른 시스템을 향해', '프로그래밍']], fresh: [['Agent-to-Agent', '에이전트끼리 소통하기 시작했어요.', 'AI 인프라'], ['Context Engineering', '프롬프트를 넘어, 맥락을 설계하는 기술.', '개발 도구'], ['Spec-driven Development', '명세에서 시작하는 새로운 개발 방식.', '개발 문화']], rising: [['React Server Components', '서버 중심 렌더링이 다시 대화의 중심으로.', '웹 프레임워크'], ['WebAssembly', '브라우저 밖으로 넓어지는 가능성.', '개발 환경'], ['Edge Computing', '사용자와 더 가까운 곳에서 실행해요.', '인프라']] },
  { id: 'fashion', name: '패션', icon: '♧', summary: '옷장 속 오래된 아이템이 새로운 조합을 만납니다. 스타일의 기준은 유행보다 나만의 이야기입니다.', insight: '빠르게 바뀌는 유행에서, 오래 남는 취향으로.', keywords: ['Archive Fashion', 'Secondhand', 'Upcycling', 'Personal Style'], top: [['Neo Vintage', '시간이 만든 스타일을 지금의 감각으로', '빈티지'], ['Ballet Sneakers', '가벼운 실루엣과 스포티한 감각의 만남', '슈즈'], ['Utility Wear', '실용성이 곧 스타일이 되는 순간', '스트리트'], ['Suede Bags', '부드러운 질감이 만드는 자연스러운 멋', '액세서리'], ['Modern Prep', '단정함에 더하는 새로운 비율', '스타일']], fresh: [['Poetcore', '문학적인 분위기를 입는 방식.', '스타일'], ['Hybrid Footwear', '서로 다른 신발의 경계가 사라져요.', '슈즈'], ['Reworked Denim', '이미 있는 데님에서 시작하는 새 옷.', '업사이클링']], rising: [['Archive Fashion', '과거 컬렉션이 새로운 영감으로.', '빈티지'], ['Gorpcore', '아웃도어가 일상에 다시 스며들어요.', '스타일'], ['Handmade Accessories', '손으로 만든 디테일을 찾아요.', '액세서리']] },
];

function getPeriod(period?: string): Period {
  return period === '7d' ? 'week' : period === '30d' ? 'month' : 'day';
}

export function getMockCategory(category?: string): MockCategory {
  return mockCategories.find((item) => item.id === category || item.name === category) ?? mockCategories[0];
}

export function getMockTrends(kind: 'top' | 'new' | 'rising', params?: TrendFilterParams): Trend[] {
  if (!params?.category) {
    return mockCategories.filter((category) => category.id === 'dev' || category.id === 'fashion').flatMap((category) => getMockTrends(kind, { ...params, category: category.id })).sort((a, b) => b.mentionCount - a.mentionCount).slice(0, kind === 'top' ? 5 : 3);
  }
  const category = getMockCategory(params?.category);
  const period = getPeriod(params?.period);
  const entries = kind === 'top' ? category.top : kind === 'new' ? category.fresh : category.rising;
  const order = kind === 'top' ? (period === 'week' ? [2, 0, 1, 3, 4] : period === 'month' ? [1, 3, 0, 4, 2] : [0, 1, 2, 3, 4]) : [0, 1, 2];
  const categoryFactor = 1 - mockCategories.indexOf(category) * 0.047;
  const periodFactor = period === 'day' ? 1 : period === 'week' ? 5.8 : 21.4;

  return order.map((entryIndex, rank) => ({
    trendId: `${category.id}-${kind}-${entryIndex}`,
    keyword: entries[entryIndex][0],
    description: entries[entryIndex][1],
    tag: entries[entryIndex][2],
    category: category.name,
    mentionCount: Math.round((kind === 'top' ? [24860, 18420, 15730, 12580, 9240][rank] : kind === 'new' ? [1840, 1260, 890][rank] : [6240, 4530, 3260][rank]) * categoryFactor * periodFactor),
    growthRate: Math.round((kind === 'top' ? [128.4, 86.2, 214.6, 42.8, 23.1][entryIndex] : kind === 'new' ? [0, 0, 0][rank] : [186, 142, 98][rank]) * (period === 'day' ? 1 : period === 'week' ? 0.82 : 0.61) * 10) / 10,
    change: kind === 'new' ? 'NEW' : (period === 'day' ? [2, 3, 'NEW', -1, 0] : period === 'week' ? [1, -1, 2, 0, 'NEW'] : [2, 0, 1, -2, 3])[rank] as number | 'NEW',
    kind,
    period,
  }));
}

export function getMockAllTrends(): Trend[] {
  return mockCategories.flatMap((category) => (['top', 'new', 'rising'] as const).flatMap((kind) => getMockTrends(kind, { category: category.id })));
}

export function getMockTrendDetail(trendId: string): TrendDetail | undefined {
  const trend = getMockAllTrends().find((item) => item.trendId === trendId);
  return trend ? { ...trend, firstDetectedAt: '2026-08-21T00:00:00+09:00', updatedAt: '2026-09-03T00:00:00+09:00' } : undefined;
}

export function getMockTrendAnalysis(trendId: string): TrendAnalysis {
  const trend = getMockTrendDetail(trendId);
  const category = getMockCategory(trend?.category);
  return {
    trendId,
    reason: trend ? `${trend.keyword} 관련 사례가 새로운 흐름으로 확산` : '관련 콘텐츠에서 새로운 흐름이 시작',
    description: `${category.summary} ${trend?.keyword ?? '이 트렌드'}가 지금 새로운 흐름으로 이어지고 있습니다.`,
  };
}

export function getMockRelatedKeywords(trendId: string): RelatedKeyword[] {
  const trend = getMockTrendDetail(trendId);
  if (!trend) return [];
  return getMockAllTrends()
    .filter((item) => item.category === trend.category && item.trendId !== trendId)
    .slice(0, 4)
    .map((item, index) => ({ trendId: item.trendId, keyword: item.keyword, relevance: 0.8 - index * 0.08 }));
}

export function getMockRelatedContents(trendId: string): TrendContent[] {
  const trend = getMockTrendDetail(trendId);
  if (!trend) return [];
  return [
    { contentId: `${trendId}-content-1`, title: `${trend.keyword}, 지금 주목해야 하는 이유`, url: '#', source: 'Trend Editorial', publishedAt: '2026-09-01' },
    { contentId: `${trendId}-content-2`, title: `${trend.keyword}로 읽는 새로운 흐름`, url: '#', source: 'Trend Brief', publishedAt: '2026-08-31' },
    { contentId: `${trendId}-content-3`, title: `이번 주 ${trend.category}에서 함께 떠오른 키워드`, url: '#', source: 'Trend Report', publishedAt: '2026-08-30' },
  ];
}
