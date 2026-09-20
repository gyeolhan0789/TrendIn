import { getTrendContents, getTrends } from './api/trendApi';
import type { Trend, TrendContent } from './types/trend';

export interface FeaturedTrendContent {
  trend: Trend;
  content: TrendContent;
}

/**
 * 인기 트렌드 1~4위마다 가장 최근에 수집된 콘텐츠 하나를 홈에 노출합니다.
 * 분야는 홈에서 고른 것을 그대로 받습니다. 위 트렌드 판과 다른 분야를 보여 주면 한 화면이 두 말을 합니다.
 */
export async function getFeaturedTrendContents(domain: string): Promise<FeaturedTrendContent[]> {
  const { trends } = await getTrends({
    domain,
    type: 'CURRENT',
    period: '24H',
    page: 0,
    size: 4,
  });
  const rankedTrends = trends
    .filter((trend) => Number.isInteger(trend.trendId) && trend.trendId > 0)
    .sort((left, right) => (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER))
    .slice(0, 4);
  const contents = await Promise.allSettled(
    rankedTrends.map((trend) => getTrendContents(trend.trendId, 0, 1)),
  );

  return contents.flatMap((result, index) => {
    if (result.status !== 'fulfilled') return [];
    const content = result.value.content.find((item) => item.url.trim().length > 0);
    return content ? [{ trend: rankedTrends[index], content }] : [];
  });
}
