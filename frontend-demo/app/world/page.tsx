import type { Metadata } from 'next';
import WorldExplorer from '../_components/world-explorer';
import { getTrend } from '../trends';
export const metadata: Metadata = {
  title: 'ahead. — 세계 추이 · 국가별 관심과 확산', description: '1일·7일 국가별 관심도와 30일 확산 경로를 살펴보는 트렌드 예시. 실제 전파를 증명하는 데이터가 아닙니다.',
  openGraph: { title: 'ahead. — 세계 추이 · 국가별 관심과 확산', description: '같은 흐름, 다른 온도. 국가별 관심도와 30일 확산 흐름을 살펴보세요.' },
  twitter: { card: 'summary', title: 'ahead. — 세계 추이 · 국가별 관심과 확산', description: '1일·7일 국가별 관심도와 30일 확산 흐름.' },
};
export default async function Page({ searchParams }: { searchParams: Promise<{ trend?: string | string[] }> }) {
  const params = await searchParams;
  const id = typeof params.trend === 'string' && getTrend(params.trend) ? params.trend : '';
  return <WorldExplorer key={id} initialTrend={id}/>;
}
