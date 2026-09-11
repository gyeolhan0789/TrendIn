import type { Trend } from '../trend/types/trend';
import type { InterestKeyword, RecommendedKeyword } from './types/myPage';

/**
 * 이미 등록한 키워드와 같은 카테고리를 먼저 권하고, 남는 자리는 언급량이 많은 순서로 채웁니다.
 * 무엇 때문에 권했는지 카드에 한 줄로 밝혀야 해서 근거가 된 키워드를 함께 들고 다닙니다.
 */
export function recommendKeywords(catalog: Trend[], keywords: InterestKeyword[], limit = 3): RecommendedKeyword[] {
  const registeredTrendIds = new Set(keywords.map((keyword) => keyword.trendId).filter(Boolean));
  const registeredNames = new Set(keywords.map((keyword) => keyword.keyword));

  const seedByCategory = new Map<string, string>();
  keywords.forEach((keyword) => {
    const seed = catalog.find((trend) => trend.trendId === keyword.trendId);
    if (seed && !seedByCategory.has(seed.category)) seedByCategory.set(seed.category, seed.keyword);
  });

  const available = new Map<string, Trend>();
  catalog.forEach((trend) => {
    if (registeredTrendIds.has(trend.trendId) || registeredNames.has(trend.keyword)) return;
    // 같은 키워드가 여러 묶음에 걸쳐 있을 수 있어 언급량이 큰 쪽만 남깁니다.
    const current = available.get(trend.keyword);
    if (!current || trend.mentionCount > current.mentionCount) available.set(trend.keyword, trend);
  });

  return [...available.values()]
    .sort((a, b) => {
      const related = Number(seedByCategory.has(b.category)) - Number(seedByCategory.has(a.category));
      return related !== 0 ? related : b.mentionCount - a.mentionCount;
    })
    .slice(0, limit)
    .map((trend) => ({
      trendId: trend.trendId,
      keyword: trend.keyword,
      reason: seedByCategory.has(trend.category) ? `${seedByCategory.get(trend.category)} 관련` : `${trend.category} 카테고리 인기`,
    }));
}
