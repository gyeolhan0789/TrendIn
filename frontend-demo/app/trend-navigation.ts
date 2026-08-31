import { categories, getCategory, getTrend, getTrends, type CategoryId, type Trend } from './trends';

export const searchHref = (trend: Trend) => `/search?${new URLSearchParams({ q: trend.name, category: trend.category })}`;
export const worldHref = (trend: Trend) => `/world?${new URLSearchParams({ trend: trend.id })}`;
export const validCategory = (value: unknown): CategoryId | undefined => categories.find(c => c.id === value)?.id;
export function worldSelection(id: string, fallback: CategoryId) {
  const requested = getTrend(id);
  const category = getCategory(requested?.category ?? fallback);
  const top = getTrends(category.id, 'top', 'month');
  const trend = requested ? getTrends(category.id, requested.kind, 'month').find(t => t.id === requested.id)! : top[0];
  return { category, trend, options: requested && requested.kind !== 'top' ? [...top, trend] : top };
}
