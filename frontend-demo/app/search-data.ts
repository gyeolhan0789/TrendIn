import { allTrends, getCategory, type CategoryId, type Trend } from './trends';

export type SearchScope = 'interests' | CategoryId;
export type SearchKind = 'all' | Trend['kind'];
export type SearchSort = 'relevance' | 'mentions' | 'growth';
export const kindLabels = { top: '현재 트렌드', new: '신규 등장', rising: '급상승' };
const aliases: Record<string, string> = {
  'AI Agent': 'AI 에이전트 인공지능', 'Vibe Coding': '바이브 코딩', MCP: '모델 컨텍스트 프로토콜', 'Local LLM': '로컬 언어 모델', Rust: '러스트',
  'Neo Vintage': '네오 빈티지', 'Ballet Sneakers': '발레 스니커즈 운동화', 'Utility Wear': '유틸리티 웨어', 'Suede Bags': '스웨이드 가방', 'Modern Prep': '모던 프레피',
  'Cozy Co-op': '코지 협동', 'AI NPC': '인공지능 엔피씨', 'Handheld Gaming': '휴대용 게임', 'React Server Components': '리액트 서버 컴포넌트',
  'Agent-to-Agent': '에이전트', 'Context Engineering': '컨텍스트 엔지니어링 맥락', 'Archive Fashion': '아카이브 패션', 'Gorpcore': '고프코어',
};
export const normalizeSearch = (s: string) => s.normalize('NFKC').toLocaleLowerCase().replace(/[\s_-]+/g, '');
export function searchTrends({ query, scope, interests, kind, sort, savedOnly, saved }: {
  query: string; scope: SearchScope; interests: CategoryId[]; kind: SearchKind; sort: SearchSort; savedOnly: boolean; saved: string[];
}): Trend[] {
  const tokens = query.trim().split(/\s+/).map(normalizeSearch).filter(Boolean);
  return allTrends.filter(t => (scope === 'interests' ? interests.includes(t.category) : t.category === scope) &&
    (kind === 'all' || kind === t.kind) && (!savedOnly || saved.includes(t.id)))
    .map(trend => {
      const c = getCategory(trend.category);
      const fields = [[trend.name, 10], [aliases[trend.name] ?? '', 8], [trend.tag, 5], [trend.sub, 3], [c.name, 1], [c.keywords.join(' '), 1]] as const;
      const scores = tokens.map(token => Math.max(0, ...fields.map(([field, weight]) => normalizeSearch(field).includes(token) ? weight : 0)));
      return { trend, matches: scores.every(s => s > 0), score: scores.reduce((a, b) => a + b, 0) + (normalizeSearch(trend.name) === normalizeSearch(query) ? 20 : 0) };
    }).filter(t => t.matches).sort((a, b) =>
      (sort === 'relevance' ? b.score - a.score : sort === 'growth' ? b.trend.growth - a.trend.growth : 0) || b.trend.mentions - a.trend.mentions || a.trend.id.localeCompare(b.trend.id))
    .map(({ trend }) => trend);
}
