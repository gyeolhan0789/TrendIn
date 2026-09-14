import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { PageContainer } from '../../components/layout/PageContainer';
import { SavedTrendCard } from '../../features/savedTrend/components/SavedTrendCard';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import type { SavedTrend } from '../../features/savedTrend/types/savedTrend';

interface SavedOverview {
  total: number;
  rising: SavedTrend[];
  fresh: SavedTrend[];
  falling: SavedTrend[];
}

/** 지표가 아직 없는 트렌드는 오름과 내림 어느 쪽에도 넣지 않습니다. */
function summarise(trends: SavedTrend[]): SavedOverview {
  const withGrowth = trends.filter((trend) => trend.growthRate !== null);
  return {
    total: trends.length,
    rising: withGrowth.filter((trend) => (trend.growthRate ?? 0) > 0).sort((a, b) => (b.growthRate ?? 0) - (a.growthRate ?? 0)),
    fresh: trends.filter((trend) => trend.trendTypes.includes('NEW')),
    falling: withGrowth.filter((trend) => (trend.growthRate ?? 0) < 0).sort((a, b) => (a.growthRate ?? 0) - (b.growthRate ?? 0)),
  };
}

function SavedOverviewCards({ overview }: { overview: SavedOverview }) {
  const leader = overview.rising[0];
  const newest = overview.fresh[0];
  const weakest = overview.falling[0];

  return (
    <div className="saved-overview" aria-label="저장한 트렌드 요약">
      <div className="saved-overview-card">
        <span>오르는 중</span>
        <strong className="is-rising">{overview.rising.length}<small>/ {overview.total}</small></strong>
        <p>{leader ? `${leader.keyword} +${leader.growthRate}% 선두` : '—'}</p>
      </div>
      <div className="saved-overview-card">
        <span>새로 등장</span>
        <strong className="is-new">{overview.fresh.length}<small>/ {overview.total}</small></strong>
        <p>{newest ? `${newest.keyword} 처음 등장` : '—'}</p>
      </div>
      <div className="saved-overview-card">
        <span>주의 · 하락 전환</span>
        <strong className="is-falling">{overview.falling.length}<small>/ {overview.total}</small></strong>
        <p>{weakest ? `${weakest.keyword} ${weakest.growthRate}%` : '없음'}</p>
      </div>
    </div>
  );
}

function SavedEmpty() {
  return (
    <div className="saved-empty">
      <p>저장한 트렌드는 언급량과 증감을 이어서 보여 줍니다.</p>
      <h2>대시보드에서 마음에 드는 키워드의 북마크를 눌러보세요.</h2>
      <Link className="saved-empty-action" to="/">오늘의 흐름 살펴보기<span aria-hidden="true">→</span></Link>
    </div>
  );
}

export function SavedTrendPage() {
  const savedTrendsQuery = useSavedTrends();

  const trends = useMemo(() => savedTrendsQuery.data?.trends ?? [], [savedTrendsQuery.data]);
  const overview = useMemo(() => summarise(trends), [trends]);
  const isReady = savedTrendsQuery.isSuccess;

  return (
    <PageContainer>
      <div className="saved-page">
        <div className="saved-titlebar">
          <h1>저장한 트렌드</h1>
          <p>{trends.length > 0
            ? `키워드 ${trends.length}개 · 최근에 담은 것부터 보여 줍니다`
            : '담아 둔 흐름의 언급량과 증감을 이어서 봅니다'}</p>
        </div>

        {savedTrendsQuery.isLoading && <div className="saved-loading" aria-label="불러오는 중"><span /><span /><span /></div>}
        {savedTrendsQuery.isError && <ErrorState message="저장한 트렌드를 불러오지 못했습니다." onRetry={() => savedTrendsQuery.refetch()} />}

        {isReady && trends.length === 0 && <SavedEmpty />}
        {isReady && trends.length > 0 && (
          <>
            <SavedOverviewCards overview={overview} />
            <div className="saved-panel-grid">
              {trends.map((trend) => <SavedTrendCard key={trend.savedTrendId} trend={trend} />)}
            </div>
            {savedTrendsQuery.data?.hasNext && (
              <p className="saved-more-note">담은 트렌드가 많아 최근 {trends.length}개만 보여 줍니다.</p>
            )}
          </>
        )}
      </div>
    </PageContainer>
  );
}
