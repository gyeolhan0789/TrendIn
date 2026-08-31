import type { Metadata } from 'next';
import SearchExplorer from '../_components/search-explorer';
import { validCategory } from '../trend-navigation';
export const metadata: Metadata = {
  title: 'ahead. — 트렌드 검색', description: '관심 분야와 키워드로 현재·신규·급상승 트렌드를 탐색하세요. 디자인 검토용 예시 데이터 검색입니다.',
  openGraph: { title: 'ahead. — 트렌드 검색', description: '다음 관심사는, 어디에? 키워드 하나로 시작하는 발견.' },
  twitter: { card: 'summary', title: 'ahead. — 트렌드 검색', description: '키워드에서 시작해 새로운 흐름까지.' },
};
export default async function Page({ searchParams }: { searchParams: Promise<{ q?: string | string[]; category?: string | string[] }> }) {
  const params = await searchParams;
  const query = (typeof params.q === 'string' ? params.q : '').slice(0, 100);
  const category = validCategory(params.category);
  return <SearchExplorer key={`${query}:${category ?? ''}`} initialQuery={query} initialCategory={category}/>;
}
