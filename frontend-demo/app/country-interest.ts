import type { Trend } from './trends';
import { countries, type CountryId } from './world-data';

export type InterestPeriod = 'day' | 'week';
export const interestPeriods = {
  day: { label: '1일', range: '2026.08.30', axis: ['00시', '04시', '08시', '12시', '16시', '20시', '24시'] },
  week: { label: '7일', range: '2026.08.24 — 08.30', axis: ['08.24', '08.25', '08.26', '08.27', '08.28', '08.29', '08.30'] },
} as const;
const baseScores: Record<CountryId, number> = { US: 83, GB: 64, DE: 57, KR: 76, JP: 70, AU: 48 };
// Preserve the original interest-index examples. These independent illustrative
// series are not aggregates of the separate 30-day spread-story mention counts.
const hash = (s: string) => [...s].reduce((value, char) => (value * 31 + char.charCodeAt(0)) % 997, 7);
// Deterministic UI fixtures, not measured geographic trend data.
export function countrySeries(trendId: string, countryId: CountryId, period: InterestPeriod): number[] {
  const country = countries.find(c => c.id === countryId)!;
  const seed = hash(`${trendId}:${countryId}:${period}`);
  const end = Math.max(25, Math.min(98, baseScores[country.id] + seed % 29 - 14));
  const start = Math.max(10, end - 17 - seed % 28);
  const wiggle = [0, 2, -3, 4, -2, 1, 0];
  return wiggle.map((n, i) => Math.round(start + (end - start) * i / 6 + n));
}
export function worldStats(trend: Trend, period: InterestPeriod) {
  return countries.map(country => {
    const series = countrySeries(trend.id, country.id, period);
    return { ...country, series, score: series[6], change: series[6] - series[0] };
  }).sort((a, b) => b.score - a.score);
}
