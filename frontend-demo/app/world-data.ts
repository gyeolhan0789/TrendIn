import { type CategoryId, type Trend } from './trends';

export const countries = [
  { id: 'US', name: '미국', en: 'United States', lon: -100, lat: 39 },
  { id: 'GB', name: '영국', en: 'United Kingdom', lon: -3, lat: 55 },
  { id: 'DE', name: '독일', en: 'Germany', lon: 10, lat: 51 },
  { id: 'KR', name: '대한민국', en: 'South Korea', lon: 127.5, lat: 36 },
  { id: 'JP', name: '일본', en: 'Japan', lon: 139, lat: 38 },
  { id: 'AU', name: '호주', en: 'Australia', lon: 134, lat: -25 },
] as const;
export type CountryId = typeof countries[number]['id'];
export const projectPoint = (lon: number, lat: number) => ({ x: (lon + 180) / 360 * 1000, y: (85 - lat) / 145 * 460 });
export const LAST_DAY = 29;
export const dayLabel = (day: number) => `08.${String(Math.max(0, Math.min(LAST_DAY, day)) + 1).padStart(2, '0')}`;
export type Observation = {
  country: typeof countries[number]; firstDay: number; parent: CountryId | null;
  dailyMentions: number[]; context: string;
};
export type SpreadStory = { trendId: string; observations: Observation[] };

// Authored fictional scenarios. Parent links are illustrative hypotheses,
// never inferred from timing alone and never claims about real transmission.
const orders: Record<CategoryId, CountryId[]> = {
  dev: ['US', 'GB', 'DE', 'JP', 'KR', 'AU'], fashion: ['JP', 'KR', 'US', 'GB', 'DE', 'AU'],
  game: ['JP', 'US', 'KR', 'GB', 'DE', 'AU'], travel: ['GB', 'DE', 'US', 'AU', 'JP', 'KR'],
  beauty: ['KR', 'JP', 'US', 'GB', 'AU', 'DE'], music: ['KR', 'JP', 'US', 'GB', 'DE', 'AU'],
  content: ['US', 'KR', 'JP', 'GB', 'DE', 'AU'], finance: ['GB', 'US', 'DE', 'AU', 'KR', 'JP'],
  sports: ['US', 'AU', 'GB', 'DE', 'JP', 'KR'],
};
const contexts = ['작은 커뮤니티에서 첫 언급이 관측되는 장면', '소개·해설 콘텐츠가 현지에 등장하는 장면', '관련 키워드가 다른 언어권에서도 관측되는 장면', '현지 사용 후기와 사례가 늘어나는 장면', '커뮤니티를 넘어 여러 채널에서 언급되는 장면', '새로운 지역의 대화로 이어지는 장면'];
export function getSpreadStory(trend: Trend): SpreadStory {
  const variation = Number(trend.id.split('-').at(-1)) || 0;
  const order = [...orders[trend.category]];
  if (variation % 2) [order[0], order[1]] = [order[1], order[0]];
  const days = [variation % 3, 4 + variation % 3, 9 + variation % 2, 14 + variation % 3, 20 + variation % 2, 26 + variation % 3];
  const parentIndex = [null, 0, 0, 1, 2, 3];
  return { trendId: trend.id, observations: order.map((id, index) => {
    const firstDay = days[index];
    const base = 9 + variation * 3 + index * 2;
    return {
      country: countries.find(c => c.id === id)!, firstDay,
      parent: parentIndex[index] === null ? null : order[parentIndex[index]!],
      dailyMentions: Array.from({ length: 30 }, (_, day) => day < firstDay ? 0 : Math.round(base + (day - firstDay) * (3.1 + (5 - index) * .7) + [0, 4, -2, 5, 1][(day - firstDay) % 5])),
      context: contexts[index],
    };
  }) };
}
export function spreadAtDay(story: SpreadStory, rawDay: number) {
  const day = Math.max(0, Math.min(LAST_DAY, Math.round(Number.isFinite(rawDay) ? rawDay : 0)));
  const reached = story.observations.filter(o => o.firstDay <= day);
  return {
    day, reached,
    newlyReached: reached.filter(o => o.firstDay === day),
    links: reached.filter(o => o.parent && reached.some(source => source.country.id === o.parent)),
    mentions: reached.reduce((sum, o) => sum + o.dailyMentions[day], 0),
    latest: reached.at(-1) ?? null,
  };
}
export function spreadCurve(source: Observation, target: Observation) {
  const a = projectPoint(source.country.lon, source.country.lat);
  const b = projectPoint(target.country.lon, target.country.lat);
  const lift = Math.min(115, Math.max(25, Math.abs(b.x - a.x) * .22));
  const cx = (a.x + b.x) / 2;
  const cy = Math.max(8, Math.min(a.y, b.y) - lift);
  // End before the destination bubble, so the arrowhead stays visible.
  const dx = b.x - cx, dy = b.y - cy, length = Math.hypot(dx, dy) || 1;
  const clearance = Math.min(32, length * .8);
  return `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x - dx / length * clearance} ${b.y - dy / length * clearance}`;
}
