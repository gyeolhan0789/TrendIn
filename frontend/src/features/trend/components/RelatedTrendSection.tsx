import type { TrendFilterParams } from '../types/trend';
import { useRelatedTrends } from '../hooks/useRelatedTrends';
import { EmptyState } from '../../../components/common/EmptyState';
import { ErrorState } from '../../../components/common/ErrorState';
import { Skeleton } from '../../../components/common/Skeleton';
import { TrendCard } from './TrendCard';

export function RelatedTrendSection({ params }: { params: TrendFilterParams }) {
  const query = useRelatedTrends(params);
  if (query.isLoading) return <section className="insight-section"><div className="insight-copy"><p className="eyebrow">↗ CONNECT THE DOTS</p><h2>관심 분야에서 이어지는 새로운 흐름</h2></div><div className="insight-keywords"><div className="keyword-heading"><h3>관심 분야 연관 트렌드</h3></div><div className="keyword-list"><Skeleton count={4} /></div></div></section>;
  if (query.isError) return <section className="insight-section"><div className="insight-copy"><p className="eyebrow">↗ CONNECT THE DOTS</p><h2>관심 분야 연관 트렌드</h2></div><div className="insight-keywords"><ErrorState onRetry={() => query.refetch()} /></div></section>;
  if (query.data?.length === 0) return <section className="insight-section"><div className="insight-copy"><p className="eyebrow">↗ CONNECT THE DOTS</p><h2>관심 분야 연관 트렌드</h2></div><div className="insight-keywords"><EmptyState /></div></section>;
  return <section className="insight-section"><div className="insight-copy"><p className="eyebrow">↗ CONNECT THE DOTS</p><h2>따로 보이던 키워드가,<br />하나의 흐름으로 이어지고 있어요.</h2><p>관심 분야에서 함께 떠오르는 흐름을 살펴보세요.</p></div><div className="insight-keywords"><div className="keyword-heading"><h3>관심 분야 연관 트렌드</h3><span>지금 함께 떠오르는 흐름</span></div><div className="keyword-list">{query.data?.slice(0, 5).map((trend, index) => <TrendCard key={trend.trendId} trend={trend} rank={index + 1} variant="compact" />)}</div></div></section>;
}
