import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { PageContainer } from '../../components/layout/PageContainer';
import { AddInterestKeywordButton } from '../../features/myPage/components/AddInterestKeywordButton';
import { BookmarkButton } from '../../features/savedTrend/components/BookmarkButton';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { useTrendRelatedKeywords } from '../../features/trend/hooks/useTrendRelatedKeywords';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { ANALYSIS_PERIODS, parsePeriod, resolveDomainCode } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import type { Trend, TrendAnalysisWindow, TrendListParams } from '../../features/trend/types/trend';

const periodCopy: Record<PeriodCode, { description: string; headline: string }> = {
  '24H': { description: '하루 동안의 트렌드', headline: '하루 동안' },
  '7D': { description: '일주일 동안의 트렌드', headline: '일주일 동안' },
  '30D': { description: '한 달 동안의 트렌드', headline: '한 달 동안' },
};

const weekdays = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];

function formatDate(date: Date) {
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
}

/*
 * 분석 구간은 서버가 Asia/Seoul 자정 경계로 잘라 줍니다. 보는 사람의 시간대로 바꾸면
 * 경계가 자정이 아니게 되어 헷갈리므로, 받은 문자열의 날짜 부분을 그대로 씁니다.
 */
function formatWindowDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[2]}.${match[3]}` : value;
}

function describeWindow(window: TrendAnalysisWindow | null) {
  if (!window) return undefined;
  return `${formatWindowDate(window.recentStart)} ~ ${formatWindowDate(window.recentEnd)} 집계 · 직전 구간과 비교`;
}

/** 이전 구간 언급량이 없으면 서버가 증가율을 비워 둡니다. 그때는 숫자 대신 없다고 밝힙니다. */
function formatGrowthRate(trend: Trend) {
  if (trend.growthRate === null) return '—';
  return `${trend.growthRate > 0 ? '+' : ''}${trend.growthRate}%`;
}

function formatDelta(amount: number) {
  return `${amount >= 0 ? '+' : ''}${amount.toLocaleString()}건`;
}

function TrendKeyword({ trend, className = '' }: { trend: Trend; className?: string }) {
  const [searchParams] = useSearchParams();
  const search = searchParams.toString();
  return (
    <Link className={`home-keyword ${className}`} to={{ pathname: `/trends/${trend.trendId}`, search: search ? `?${search}` : '' }}>
      {trend.keyword}
    </Link>
  );
}

function HomeState({ loading, error, empty, onRetry }: { loading: boolean; error: boolean; empty: boolean; onRetry: () => void }) {
  if (loading) return <div className="home-loading" aria-label="불러오는 중"><span /><span /><span /></div>;
  if (error) return <ErrorState onRetry={onRetry} />;
  if (empty) return <EmptyState />;
  return null;
}

function Spotlight({ trend }: { trend: Trend }) {
  return (
    <article className="home-spotlight">
      <div className="home-spotlight-copy">
        <div className="home-row-meta">
          <span className="home-rank home-rank--spot">{String(trend.rank ?? 1).padStart(2, '0')}</span>
          {trend.trendTypes.includes('RISING') && <span className="home-rise-badge">급상승</span>}
          {trend.trendTypes.includes('NEW') && <span className="home-blue-badge">새로 등장</span>}
          <span className="home-muted-meta">{trend.domain.name}</span>
          <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} />
        </div>
        <div className="home-spotlight-title-row">
          <h3><TrendKeyword trend={trend} className="home-keyword--spotlight" /></h3>
          <span className="home-growth"><strong>{formatGrowthRate(trend)}</strong><small>직전 구간 대비</small></span>
        </div>
      </div>
      <div className="home-evidence">
        <span className="home-evidence-icon" aria-hidden="true">💡</span>
        <p><span>{trend.description}</span></p>
        <div className="home-source-list">
          <span className="home-mention-count">언급량 <strong>{trend.mentionCount.toLocaleString()}건</strong></span>
          <span>직전 구간 {trend.previousMentionCount.toLocaleString()}건</span>
          <span>{formatDelta(trend.growthAmount)}</span>
        </div>
      </div>
    </article>
  );
}

function RankingRows({ trends, startRank }: { trends: Trend[]; startRank: number }) {
  return (
    <div className="home-ranking-table">
      <div className="home-ranking-head"><span>순위</span><span>키워드</span><span>언급량</span><span>직전 구간</span><span>증감</span><span /></div>
      {trends.map((trend, index) => (
        <div className="home-ranking-row" key={trend.trendId}>
          <span className="home-rank">{String(trend.rank ?? startRank + index).padStart(2, '0')}</span>
          <span className="home-ranking-keyword"><TrendKeyword trend={trend} /><small>{trend.domain.name}</small></span>
          <span className="home-number">{trend.mentionCount.toLocaleString()}건</span>
          <span className="home-number">{trend.previousMentionCount.toLocaleString()}건</span>
          <strong className={trend.growthRate !== null && trend.growthRate < 0 ? 'is-muted' : ''}>{formatGrowthRate(trend)}</strong>
          <span className="home-row-action"><BookmarkButton trendId={trend.trendId} keyword={trend.keyword} /></span>
        </div>
      ))}
    </div>
  );
}

function FreshCard({ trend }: { trend: Trend }) {
  return (
    <Link className="home-fresh-card" to={`/trends/${trend.trendId}`}>
      <span>{trend.keyword}</span>
      <small>{trend.description}</small>
    </Link>
  );
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [domainMenuOpen, setDomainMenuOpen] = useState(false);
  const today = useMemo(() => new Date(), []);

  const domainsQuery = useDomains();
  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);
  // 분야 목록은 서버가 알려 줍니다. 아직 받지 못했으면 고를 분야가 없어 조회를 멈춰 둡니다.
  const domain = resolveDomainCode(searchParams.get('domain'), domains);
  const period = parsePeriod(searchParams.get('period'));
  const selectedDomain = domains.find((option) => option.domain === domain);

  const baseParams: Omit<TrendListParams, 'type'> | undefined = domain ? { domain, period } : undefined;
  const topQuery = useTrends(baseParams && { ...baseParams, type: 'CURRENT', size: 5 });
  const newQuery = useTrends(baseParams && { ...baseParams, type: 'NEW', size: 4 });
  const risingQuery = useTrends(baseParams && { ...baseParams, type: 'RISING', size: 4 });

  const topTrends = topQuery.data?.trends ?? [];
  const spotlight = topTrends[0];
  // 홈 전체를 아우르는 연관 키워드 조회가 없어, 가장 많이 언급된 키워드를 기준으로 보여 줍니다.
  const relatedQuery = useTrendRelatedKeywords(spotlight?.trendId);
  const windowLabel = describeWindow(topQuery.data?.analysisWindow ?? null);

  const updateFilter = (key: 'domain' | 'period', value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    setSearchParams(next);
    setDomainMenuOpen(false);
  };

  const discoveryLoading = newQuery.isLoading || risingQuery.isLoading;
  const discoveryError = newQuery.isError || risingQuery.isError;

  return (
    <PageContainer>
      <div className="home-page">
        <section className="home-hero">
          <p>{formatDate(today)} {weekdays[today.getDay()]} · {periodCopy[period].description}</p>
          <h1>
            {spotlight
              ? <>{periodCopy[period].headline} 가장 많이 언급된 건 <span>{spotlight.keyword}</span>, 언급량은 <span>{spotlight.mentionCount.toLocaleString()}건</span>입니다.</>
              : <>{periodCopy[period].headline}의 트렌드를 모으고 있습니다.</>}
          </h1>
        </section>

        <div className="home-filter-bar">
          <div className="home-category-control">
            <button type="button" aria-expanded={domainMenuOpen} disabled={domains.length === 0} onClick={() => setDomainMenuOpen((open) => !open)}>
              <span>{selectedDomain?.name ?? '분야'}</span><i className="home-category-chevron" aria-hidden="true" />
            </button>
            {domainMenuOpen && (
              <div className="home-category-menu">
                {domains.map((option) => (
                  <button type="button" key={option.domain} className={option.domain === domain ? 'is-selected' : ''} onClick={() => updateFilter('domain', option.domain)}>
                    {option.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="home-period-control" aria-label="트렌드 집계 기간">
            {ANALYSIS_PERIODS.map((value) => (
              <button type="button" key={value} className={period === value ? 'is-selected' : ''} onClick={() => updateFilter('period', value)}>{value}</button>
            ))}
          </div>
        </div>

        {domainsQuery.isError && <ErrorState message="분야 목록을 불러오지 못했습니다." onRetry={() => domainsQuery.refetch()} />}

        <section className="home-top-section" aria-labelledby="home-top-heading">
          <h2 id="home-top-heading">지금 눈여겨볼 TOP 5</h2>
          <HomeState
            loading={domainsQuery.isLoading || topQuery.isLoading}
            error={topQuery.isError}
            empty={topQuery.isSuccess && !spotlight}
            onRetry={() => topQuery.refetch()}
          />
          {spotlight && <><Spotlight trend={spotlight} /><RankingRows trends={topTrends.slice(1)} startRank={2} /></>}
        </section>

        <HomeState loading={discoveryLoading} error={discoveryError} empty={false} onRetry={() => { void newQuery.refetch(); void risingQuery.refetch(); }} />
        {!discoveryLoading && !discoveryError && (
          <section className="home-discovery" aria-label="새로운 발견">
            <div>
              <div className="home-discovery-heading"><h2>새로 등장</h2><span className="home-rise-badge">처음 등장한 키워드</span></div>
              {newQuery.data?.trends.length === 0 && <p className="home-muted-meta">이 구간에 새로 등장한 키워드가 없습니다.</p>}
              <div className="home-fresh-grid">
                {newQuery.data?.trends.map((trend) => <FreshCard key={trend.trendId} trend={trend} />)}
              </div>
            </div>
            <div>
              <div className="home-discovery-heading home-discovery-heading--lined"><h2>다시 급상승</h2><span className="home-blue-badge">언급량이 크게 늘어난 키워드</span></div>
              {risingQuery.data?.trends.length === 0 && <p className="home-muted-meta">이 구간에 급상승한 키워드가 없습니다.</p>}
              <div className="home-rising-list">
                {risingQuery.data?.trends.map((trend) => (
                  <div className="home-rising-row" key={trend.trendId}>
                    <span><TrendKeyword trend={trend} /><small>{formatDelta(trend.growthAmount)}</small></span>
                    <strong>{formatGrowthRate(trend)}</strong>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="home-discovery-heading home-discovery-heading--lined"><h2>{spotlight?.keyword ?? '연관'} <span>관련 키워드</span></h2></div>
              {relatedQuery.isError && <ErrorState message="연관 키워드를 불러오지 못했습니다." onRetry={() => relatedQuery.refetch()} />}
              {relatedQuery.isSuccess && relatedQuery.data.length === 0 && <p className="home-muted-meta">함께 언급된 키워드가 아직 없습니다.</p>}
              <div className="home-keyword-cloud">
                {relatedQuery.data?.slice(0, 9).map((related) => (
                  <span className="home-chip" key={related.keywordId}>
                    <span>{related.keyword}</span>
                    <AddInterestKeywordButton keywordId={related.keywordId} keyword={related.keyword} />
                  </span>
                ))}
              </div>
            </div>
          </section>
        )}

        <footer className="home-footer">
          <span>TrendIn<span>.</span></span>
          {windowLabel && <p>{windowLabel}</p>}
        </footer>
      </div>
    </PageContainer>
  );
}
