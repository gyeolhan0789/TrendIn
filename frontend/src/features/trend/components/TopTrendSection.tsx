import type { TrendFilterParams } from '../types/trend';
import { useTopTrends } from '../hooks/useTopTrends';
import { EmptyState } from '../../../components/common/EmptyState';
import { ErrorState } from '../../../components/common/ErrorState';
import { TrendCard } from './TrendCard';

export function TopTrendSection({ params, period, onPeriodChange }: { params: TrendFilterParams; period: string; onPeriodChange: (period: string) => void }) {
  const query = useTopTrends(params);
  return (
    <section className="top-section" aria-labelledby="top-heading">
      <div className="section-heading">
        <div><h2 id="top-heading">지금 눈여겨볼 <span className="top-label">TOP 5<span className="tiny-orbit" /></span></h2><p>가장 많이 이야기되고 있는, 관심 분야의 다섯 가지 흐름.</p></div>
        <div className="period-control" aria-label="트렌드 집계 기간">
          {['24h', '7d', '30d'].map((item) => <button type="button" key={item} className={period === item ? 'selected' : ''} onClick={() => onPeriodChange(item)}>{item}</button>)}
        </div>
      </div>
      {query.isLoading && <div className="trend-grid trend-grid--skeleton" aria-label="TOP 트렌드 불러오는 중">{Array.from({ length: 5 }, (_, index) => <div className={`skeleton skeleton-card skeleton-card--${index + 1}`} key={index} />)}</div>}
      {query.isError && <ErrorState onRetry={() => query.refetch()} />}
      {!query.isLoading && !query.isError && query.data?.length === 0 && <EmptyState />}
      {query.data && query.data.length > 0 && <ol className="trend-grid">{query.data.map((trend, index) => <li key={trend.trendId}><TrendCard trend={trend} rank={index + 1} /></li>)}</ol>}
    </section>
  );
}
