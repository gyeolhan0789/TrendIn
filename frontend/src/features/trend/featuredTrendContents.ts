import { getTrendContents, getTrends } from './api/trendApi';
import type { Trend, TrendContent } from './types/trend';

export interface FeaturedTrendContent {
  trend: Trend;
  content: TrendContent;
}

/** 인기 트렌드 1~4위마다 가장 최근에 수집된 콘텐츠 하나를 홈에 노출합니다. */
export async function getFeaturedTrendContents(): Promise<FeaturedTrendContent[]> {
  const { trends } = await getTrends({
    domain: 'FASHION',
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
