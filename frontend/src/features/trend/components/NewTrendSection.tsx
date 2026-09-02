import type { TrendFilterParams } from '../types/trend';
import { useNewTrends } from '../hooks/useNewTrends';
import { EmptyState } from '../../../components/common/EmptyState';
import { ErrorState } from '../../../components/common/ErrorState';
import { Skeleton } from '../../../components/common/Skeleton';
import { TrendCard } from './TrendCard';

export function NewTrendSection({ params }: { params: TrendFilterParams }) {
  const query = useNewTrends(params);
  if (query.isLoading) return <article className="discovery-card"><DiscoveryHeading title="신규 키워드" label="NEW" /><div className="discovery-items discovery-items--skeleton"><Skeleton count={3} /></div></article>;
  if (query.isError) return <article className="discovery-card"><DiscoveryHeading title="신규 키워드" label="NEW" /><ErrorState onRetry={() => query.refetch()} /></article>;
  if (query.data?.length === 0) return <article className="discovery-card"><DiscoveryHeading title="신규 키워드" label="NEW" /><EmptyState /></article>;
  return <article className="discovery-card"><DiscoveryHeading title="신규 키워드" label="NEW" /><p className="section-description">어제는 낯설었지만, 오늘은 눈여겨볼 키워드.</p><div className="discovery-items">{query.data?.slice(0, 3).map((trend, index) => <TrendCard key={trend.trendId} trend={trend} rank={index + 1} variant="compact" showMetaArrow={false} />)}</div></article>;
}

function DiscoveryHeading({ title, label }: { title: string; label: string }) { return <div className="discovery-heading"><div><h2>{title}</h2><span className="little-label">{label}</span></div><span className="text-button">더보기</span></div>; }
