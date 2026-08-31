'use client';

import Link from './page-link';
import { usePathname } from 'next/navigation';
import { searchHref, worldHref } from '../trend-navigation';
import type { Trend } from '../trends';

export default function TrendLinks({ trend }: { trend: Trend }) {
  const pathname = usePathname();
  return <nav className="trend-page-links" aria-label={`${trend.name} 이어서 탐색`}>
    {pathname !== '/world' && <Link href={worldHref(trend)}>세계 추이에서 보기 <span>↗</span></Link>}
    {pathname !== '/search' && <Link href={searchHref(trend)}>이 키워드 검색 <span>↗</span></Link>}
    {pathname !== '/' && <Link href="/">대시보드로 <span>↗</span></Link>}
  </nav>;
}
