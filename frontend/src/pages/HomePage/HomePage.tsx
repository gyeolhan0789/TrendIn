import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { PageContainer } from '../../components/layout/PageContainer';
import { useCollect } from '../../features/savedTrend/collect/collectContext';
import { useCollectHandlers } from '../../features/savedTrend/collect/useCollectHandlers';
import { useNewTrends } from '../../features/trend/hooks/useNewTrends';
import { useRelatedTrends } from '../../features/trend/hooks/useRelatedTrends';
import { useResurgingTrends } from '../../features/trend/hooks/useResurgingTrends';
import { useTopTrends } from '../../features/trend/hooks/useTopTrends';
import { Sparkline } from '../../features/trend/components/Sparkline';
import type { Trend, TrendFilterParams } from '../../features/trend/types/trend';

const categories = ['패션', '개발'];
const periods = [
  { value: '24h', label: '24H', description: '오늘의 트렌드', headline: '오늘' },
  { value: '7d', label: '7D', description: '이번 주 트렌드', headline: '이번주' },
  { value: '30d', label: '30D', description: '이번 달 트렌드', headline: '이번달' },
];
const weekdays = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
const relatedKeywordSets: Record<string, string[]> = {
  패션: ['아카이브 패션', '스웨이드 텍스처', '발레 플랫', '리워크 데님', '퍼스널 스타일', '유틸리티 웨어', '빈티지 셀렉션'],
  개발: ['사내 규칙 학습', 'PR 리뷰 대기시간', '리뷰 SLA', '코드 컨벤션 자동화', '리뷰 자동화 비용', '온디바이스 추론', '오픈모델 라이선스'],
};

function formatDate(date: Date) {
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
}

function TrendKeyword({ trend, className = '' }: { trend: Trend; className?: string }) {
  const location = useLocation();
  const collectHandlers = useCollectHandlers(trend);
  return <Link className={`home-keyword ${className}`} to={{ pathname: `/trends/${trend.trendId}`, search: location.search }} {...collectHandlers}>{trend.keyword}</Link>;
}

function BookmarkButton({ trend }: { trend: Trend }) {
  const { isSaved, toggleSave } = useCollect();
  const saved = isSaved(trend.trendId);
  return (
    <button className={`home-bookmark${saved ? ' is-saved' : ''}`} type="button" title={saved ? '담기 취소' : '담기'} aria-label={`${trend.keyword} ${saved ? '담기 취소' : '담기'}`} aria-pressed={saved} onClick={(event) => { event.preventDefault(); toggleSave(trend); }}>
      {/* 담긴 키워드는 앰버로 채우고, 해제하면 선만 남습니다. 색은 CSS에서 currentColor로 받습니다. */}
      <svg viewBox="0 0 13 16" width="13" height="16" fill={saved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.3" aria-hidden="true"><path d="M1.5 1.5h10v13l-5-3.6-5 3.6z" /></svg>
    </button>
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
          <span className="home-rank home-rank--spot">01</span>
          <span className="home-rise-badge">급등</span>
          <span className="home-muted-meta">{trend.category} · 3주 연속 상위권</span>
          <span className="home-movement">▲ {Math.max(1, trend.change === 'NEW' || !trend.change ? 2 : trend.change)}</span>
          <BookmarkButton trend={trend} />
        </div>
        <div className="home-spotlight-title-row">
          <h3><TrendKeyword trend={trend} className="home-keyword--spotlight" /></h3>
          <span className="home-growth"><strong>+{trend.growthRate}%</strong><small>7일 대비</small></span>
        </div>
      </div>
      <div className="home-spotlight-chart">
        <p>최근 14일 언급 추이</p>
        <Sparkline trend={trend} width={240} height={62} color="#c2712c" />
        <div><span>08.21</span><span>09.03</span></div>
      </div>
      <div className="home-evidence">
        <span className="home-evidence-icon" aria-hidden="true">💡</span>
        <p><span>{trend.description ?? '지금 주목받는 흐름이 여러 채널에서 빠르게 확산 중입니다.'}</span><span>관련 대화와 사례가 이어지며 관심이 커지고 있습니다.</span></p>
        <div className="home-source-list"><span className="home-mention-count">언급량 <strong>{trend.mentionCount.toLocaleString()}건</strong></span><a href="https://news.ycombinator.com" target="_blank" rel="noreferrer">해커뉴스</a><a href="https://news.hada.io" target="_blank" rel="noreferrer">GeekNews</a><span>외 9개 소스</span></div>
      </div>
    </article>
  );
}

function RankingRows({ trends }: { trends: Trend[] }) {
  return (
    <div className="home-ranking-table">
      <div className="home-ranking-head"><span>순위</span><span>추이</span><span>키워드</span><span>언급량</span><span>7일 대비</span><span>순위 변동</span><span /></div>
      {trends.map((trend, index) => {
        const change = trend.change === 'NEW' ? 'NEW' : trend.change ? `${trend.change > 0 ? '▲' : '▼'} ${Math.abs(trend.change)}` : '—';
        return (
          <div className="home-ranking-row" key={trend.trendId}>
            <span className="home-rank">{String(index + 2).padStart(2, '0')}</span>
            <Sparkline trend={trend} />
            <span className="home-ranking-keyword"><TrendKeyword trend={trend} /><small>{trend.category}{trend.tag ? ` · ${trend.tag}` : ''}</small></span>
            <span className="home-number">{trend.mentionCount.toLocaleString()}건</span>
            <strong className={trend.growthRate < 0 ? 'is-muted' : ''}>{trend.growthRate > 0 ? '+' : ''}{trend.growthRate}%</strong>
            <span className="home-change"><span className={trend.change !== 'NEW' && typeof trend.change === 'number' && trend.change < 0 ? 'is-down' : ''}>{change}</span></span>
            <span className="home-row-action"><BookmarkButton trend={trend} /></span>
          </div>
        );
      })}
    </div>
  );
}

function FreshCard({ trend }: { trend: Trend }) {
  const collectHandlers = useCollectHandlers(trend);
  return (
    <Link className="home-fresh-card" to={`/trends/${trend.trendId}`} {...collectHandlers}>
      <span>{trend.keyword}</span>
      <small>{formatShortDate(trend)} 첫 등장</small>
    </Link>
  );
}

function RelatedChip({ trend }: { trend: Trend }) {
  const collectHandlers = useCollectHandlers(trend);
  return <Link className="home-chip home-chip--collectable" to={`/trends/${trend.trendId}`} {...collectHandlers}>{trend.keyword}</Link>;
}

function DiscoverySection({ newTrends, risingTrends, relatedTrends, category }: { newTrends: Trend[]; risingTrends: Trend[]; relatedTrends: Trend[]; category: string }) {
  const fallbackKeywords = relatedKeywordSets[category] ?? [];
  return (
    <section className="home-discovery" aria-label="새로운 발견">
      <div>
        <div className="home-discovery-heading"><h2>새로 등장</h2><span className="home-rise-badge">처음 등장한 키워드</span></div>
        <div className="home-fresh-grid">
          {newTrends.slice(0, 4).map((trend) => <FreshCard key={trend.trendId} trend={trend} />)}
        </div>
      </div>
      <div>
        <div className="home-discovery-heading home-discovery-heading--lined"><h2>다시 급상승</h2><span className="home-blue-badge">다시 TOP 100 재진입</span></div>
        <div className="home-rising-list">{risingTrends.slice(0, 4).map((trend) => <div className="home-rising-row" key={trend.trendId}><span><TrendKeyword trend={trend} /><small>{Math.max(2, Math.round(trend.growthRate / 20))}주 만에</small></span><Sparkline trend={trend} color="#8092e0" /></div>)}</div>
      </div>
      <div>
        <div className="home-discovery-heading home-discovery-heading--lined"><h2>{relatedTrends[0]?.keyword ?? category} <span>관련 키워드</span></h2></div>
        {/* 실제 트렌드로 연결되는 키워드만 담을 수 있고, 나머지는 안내용 텍스트로 둡니다. */}
        <div className="home-keyword-cloud">
          {relatedTrends.slice(0, 9).map((trend) => <RelatedChip key={trend.trendId} trend={trend} />)}
          {fallbackKeywords.slice(0, Math.max(0, 9 - relatedTrends.length)).map((keyword) => <span className="home-chip" key={keyword}>{keyword}</span>)}
        </div>
      </div>
    </section>
  );
}

function formatShortDate(trend: Trend) {
  const day = Math.max(1, Math.min(28, trend.keyword.length + 2));
  return `09.${String(day).padStart(2, '0')}`;
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [now, setNow] = useState(() => new Date());
  const [categoryOpen, setCategoryOpen] = useState(false);
  const rawCategory = searchParams.get('category');
  const category = rawCategory && categories.includes(rawCategory) ? rawCategory : '패션';
  const period = searchParams.get('period') ?? '24h';
  const params: TrendFilterParams = useMemo(() => ({ category, period }), [category, period]);
  const topQuery = useTopTrends(params);
  const newQuery = useNewTrends(params);
  const risingQuery = useResurgingTrends(params);
  const relatedQuery = useRelatedTrends(params);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1_000);
    return () => window.clearInterval(timer);
  }, []);

  const updateFilter = (key: 'category' | 'period', value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    setSearchParams(next);
    setCategoryOpen(false);
  };

  const topTrends = topQuery.data ?? [];
  const spotlight = topTrends[0];
  const displayCategory = category;

  return (
    <PageContainer>
      <div className="home-page">
        <section className="home-hero">
          <p>{formatDate(now)} {weekdays[now.getDay()]} · {periods.find((item) => item.value === period)?.description ?? '오늘의 트렌드'}</p>
          <h1>{periods.find((item) => item.value === period)?.headline ?? '오늘'} 가장 빠르게 오른 건 <span>{spotlight?.keyword ?? 'AI 코드 리뷰 자동화'}</span>, 언급량이 7일 대비 <span>+{spotlight?.growthRate ?? 240}%</span> 늘었습니다.</h1>
        </section>

        <div className="home-filter-bar">
          <div className="home-category-control">
            <button type="button" aria-expanded={categoryOpen} onClick={() => setCategoryOpen((open) => !open)}><span>{displayCategory}</span><i className="home-category-chevron" aria-hidden="true" /></button>
            {categoryOpen && <div className="home-category-menu">{categories.map((item) => <button type="button" key={item} className={item === displayCategory ? 'is-selected' : ''} onClick={() => updateFilter('category', item)}>{item}</button>)}</div>}
          </div>
          <div className="home-period-control" aria-label="트렌드 집계 기간">{periods.map((item) => <button type="button" key={item.value} className={period === item.value ? 'is-selected' : ''} onClick={() => updateFilter('period', item.value)}>{item.label}</button>)}</div>
        </div>

        <section className="home-top-section" aria-labelledby="home-top-heading">
          <h2 id="home-top-heading">지금 눈여겨볼 TOP 5</h2>
          <HomeState loading={topQuery.isLoading} error={topQuery.isError} empty={!spotlight} onRetry={() => topQuery.refetch()} />
          {spotlight && <><Spotlight trend={spotlight} /><RankingRows trends={topTrends.slice(1, 5)} /></>}
        </section>

        <HomeState loading={newQuery.isLoading || risingQuery.isLoading || relatedQuery.isLoading} error={newQuery.isError || risingQuery.isError || relatedQuery.isError} empty={false} onRetry={() => { void newQuery.refetch(); void risingQuery.refetch(); void relatedQuery.refetch(); }} />
        {!newQuery.isLoading && !risingQuery.isLoading && !relatedQuery.isLoading && <DiscoverySection newTrends={newQuery.data ?? []} risingTrends={risingQuery.data ?? []} relatedTrends={relatedQuery.data ?? []} category={category} />}

        <footer className="home-footer"><span>TrendIn<span>.</span></span><p>공개 커뮤니티·커머스·검색 데이터를 60초 주기로 집계합니다.</p><small>demo dataset</small></footer>
      </div>
    </PageContainer>
  );
}
