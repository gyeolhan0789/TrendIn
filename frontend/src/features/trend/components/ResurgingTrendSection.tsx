import type { TrendFilterParams } from '../types/trend';
import { useResurgingTrends } from '../hooks/useResurgingTrends';
import { EmptyState } from '../../../components/common/EmptyState';
import { ErrorState } from '../../../components/common/ErrorState';
import { Skeleton } from '../../../components/common/Skeleton';
import { TrendCard } from './TrendCard';

export function ResurgingTrendSection({ params }: { params: TrendFilterParams }) {
  const query = useResurgingTrends(params);
  if (query.isLoading) return <article className="discovery-card rising-card"><DiscoveryHeading title="재급상승 키워드" label="RISING" /><div className="discovery-items discovery-items--skeleton"><Skeleton count={3} /></div></article>;
  if (query.isError) return <article className="discovery-card rising-card"><DiscoveryHeading title="재급상승 키워드" label="RISING" /><ErrorState onRetry={() => query.refetch()} /></article>;
  if (query.data?.length === 0) return <article className="discovery-card rising-card"><DiscoveryHeading title="재급상승 키워드" label="RISING" /><EmptyState /></article>;
  return <article className="discovery-card rising-card"><DiscoveryHeading title="재급상승 키워드" label="RISING" /><p className="section-description">알고 있던 키워드의, 모르고 있던 새로운 움직임.</p><div className="discovery-items">{query.data?.slice(0, 3).map((trend, index) => <TrendCard key={trend.trendId} trend={trend} rank={index + 1} variant="compact" showMetaArrow={false} />)}</div></article>;
}

function DiscoveryHeading({ title, label }: { title: string; label: string }) { return <div className="discovery-heading"><div><h2>{title}</h2><span className="little-label">{label}</span></div><span className="text-button">더보기</span></div>; }
