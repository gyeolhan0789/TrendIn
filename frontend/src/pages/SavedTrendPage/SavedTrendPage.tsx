import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { FilterSelect } from '../../components/common/FilterSelect';
import { SavedTrendCard } from '../../features/savedTrend/components/SavedTrendCard';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import { pageList } from '../../utils/pageList';
import type { SavedTrend } from '../../features/savedTrend/types/savedTrend';

const ALL_DOMAINS = '전체';
/* 시안이 석 줄 격자라 한 쪽을 네 줄로 끊습니다. */
const PAGE_SIZE = 12;

/** 지표가 없는 트렌드는 순서를 매길 수 없어 뒤로 보냅니다. */
function byMetric(pick: (trend: SavedTrend) => number | null) {
  return (a: SavedTrend, b: SavedTrend) => {
    const left = pick(a);
    const right = pick(b);
    if (left === null) return right === null ? 0 : 1;
    if (right === null) return -1;
    return right - left;
  };
}

/* 서버가 최근에 담은 것부터 주므로 '최근 저장순'은 받은 차례 그대로입니다. */
const comparators: Record<string, ((a: SavedTrend, b: SavedTrend) => number) | undefined> = {
  growth: byMetric((trend) => trend.growthRate),
  mentions: byMetric((trend) => trend.mentionCount),
  name: (a, b) => a.keyword.localeCompare(b.keyword, 'ko'),
};

const sorts = [
  { value: 'recent', label: '최근 저장순' },
  { value: 'growth', label: '급상승순' },
  { value: 'mentions', label: '언급량순' },
  { value: 'name', label: '가나다순' },
];

function SavedEmpty() {
  return (
    <div className="saved-empty">
      <p>아직 담아 둔 트렌드가 없습니다.</p>
      <h2>마음에 드는 키워드의 북마크를 누르면 여기에 모입니다.</h2>
      <Link className="saved-empty-action" to="/dashboard">
        트렌드 탐색에서 오늘의 흐름 보기
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </Link>
    </div>
  );
}

export function SavedTrendPage() {
  const savedTrendsQuery = useSavedTrends();
  const [selectedDomain, setSelectedDomain] = useState(ALL_DOMAINS);
  const [sort, setSort] = useState('recent');
  const [page, setPage] = useState(1);

  const trends = useMemo(() => savedTrendsQuery.data?.trends ?? [], [savedTrendsQuery.data]);

  // 담아 둔 트렌드가 있는 분야만 거르개로 내놓습니다.
  const domains = useMemo(() => {
    const seen = new Map<string, string>();
    trends.forEach((trend) => seen.set(trend.domain.code, trend.domain.name));
    return [...seen].map(([code, name]) => ({ code, name }));
  }, [trends]);

  // 고른 분야의 마지막 트렌드를 빼면 그 칸도 사라지므로, 갇히지 않게 전체로 되돌립니다.
  const activeDomain = domains.some((domain) => domain.code === selectedDomain) ? selectedDomain : ALL_DOMAINS;

  const visible = useMemo(() => {
    const filtered = activeDomain === ALL_DOMAINS
      ? trends
      : trends.filter((trend) => trend.domain.code === activeDomain);
    const comparator = comparators[sort];
    return comparator ? [...filtered].sort(comparator) : filtered;
  }, [activeDomain, sort, trends]);

  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  // 담기를 빼거나 거르개를 좁히면 쪽수가 줄어, 보던 쪽이 사라질 수 있습니다.
  const currentPage = Math.min(page, totalPages);
  const shown = visible.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const filterBy = (domain: string) => {
    setSelectedDomain(domain);
    setPage(1);
  };

  return (
    <div className="saved-page">
      <section className="saved-hero trendin-page-heading">
        <div className="saved-hero-title">
          <p className="saved-eyebrow trendin-page-eyebrow">내가 저장한 트렌드를 한눈에</p>
          <h1>저장된 트렌드</h1>
          {/* 아직 못 불러왔을 때 0 개라고 단정하지 않도록, 담긴 게 있을 때만 셉니다. */}
          {trends.length > 0 && <p className="saved-count">총 <strong>{trends.length}</strong>개</p>}
        </div>
        <FilterSelect
          value={sort}
          options={sorts}
          ariaLabel="정렬"
          onChange={(value) => { setSort(value); setPage(1); }}
          disabled={trends.length === 0}
        />
      </section>

      {domains.length > 1 && (
        <section className="saved-tabs" aria-label="분야 거르개">
          <button
            type="button"
            className={`saved-tab${activeDomain === ALL_DOMAINS ? ' is-active' : ''}`}
            aria-pressed={activeDomain === ALL_DOMAINS}
            onClick={() => filterBy(ALL_DOMAINS)}
          >
            전체
          </button>
          {domains.map((domain) => (
            <button
              key={domain.code}
              type="button"
              className={`saved-tab${activeDomain === domain.code ? ' is-active' : ''}`}
              aria-pressed={activeDomain === domain.code}
              onClick={() => filterBy(domain.code)}
            >
              {domain.name}
            </button>
          ))}
        </section>
      )}

      <section className="saved-main">
        {savedTrendsQuery.isLoading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}

        {savedTrendsQuery.isError && (
          <div className="trendin-state is-error" role="alert">
            <p>저장한 트렌드를 불러오지 못했습니다.</p>
            <button type="button" onClick={() => savedTrendsQuery.refetch()}>다시 시도</button>
          </div>
        )}

        {savedTrendsQuery.isSuccess && (
          <>
            {trends.length === 0 && <SavedEmpty />}
            {trends.length > 0 && shown.length === 0 && <p className="saved-filter-empty">이 분야에 담아 둔 트렌드가 없습니다.</p>}
            {shown.length > 0 && (
              <div className="saved-grid">
                {shown.map((trend) => <SavedTrendCard key={trend.savedTrendId} trend={trend} />)}
              </div>
            )}
            {savedTrendsQuery.data.hasNext && (
              <p className="saved-more-note">담은 트렌드가 많아 최근 {trends.length}개만 보여 줍니다.</p>
            )}
          </>
        )}
      </section>

      {totalPages > 1 && (
        <section className="saved-pagination">
          <div className="trendin-pages">
            {pageList(currentPage, totalPages).map((item, index) => (item === 'gap'
              ? <span className="trendin-page-gap" key={`gap-${index}`}>···</span>
              : (
                <button
                  key={item}
                  type="button"
                  className={item === currentPage ? 'is-current' : ''}
                  aria-current={item === currentPage ? 'page' : undefined}
                  onClick={() => setPage(item)}
                >
                  {item}
                </button>
              )))}
          </div>
        </section>
      )}
    </div>
  );
}
