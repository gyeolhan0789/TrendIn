import { getTrendContents, getTrends } from './api/trendApi';
import type { Trend, TrendContent, TrendType } from './types/trend';

export interface FeaturedTrendContent {
  trend: Trend;
  content: TrendContent;
}

/**
 * 요청한 갈래의 트렌드 1~4위마다 가장 최근에 수집된 콘텐츠 하나를 홈에 노출합니다.
 * 분야는 홈에서 고른 것을 그대로 받습니다. 위 트렌드 판과 다른 분야를 보여 주면 한 화면이 두 말을 합니다.
 */
export async function getFeaturedTrendContents(domain: string, type: TrendType): Promise<FeaturedTrendContent[]> {
  const { trends } = await getTrends({
    domain,
    type,
    period: '24H',
    page: 0,
    size: 4,
  });
  /*
   * **받은 순서를 그대로 둡니다.** 예전에는 `trend.rank` 로 다시 줄을 세웠는데, 그 값은
   * 분야 전체의 언급량 순위라 갈래가 세운 줄을 덮어썼습니다. 급상승은 서버가 증가율로
   * 줄을 세우므로, 언급량 순위로 다시 정렬하면 1~4위가 아예 다른 넷이 됩니다.
   *
   * 갈래마다 기준이 다른 것은 서버가 정합니다 (인기·신규는 언급량, 급상승은 증가율).
   */
  const rankedTrends = trends
    .filter((trend) => Number.isInteger(trend.trendId) && trend.trendId > 0)
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
