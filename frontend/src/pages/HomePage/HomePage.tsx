import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import heroWave from '../../assets/flowing-wave.webp';
import { AddInterestKeywordButton } from '../../features/myPage/components/AddInterestKeywordButton';
import { useCollect } from '../../features/savedTrend/collect/collectContext';
import { useCollectHandlers } from '../../features/savedTrend/collect/useCollectHandlers';
import { Sparkline } from '../../features/trend/components/Sparkline';
import { useNewTrends } from '../../features/trend/hooks/useNewTrends';
import { useRelatedTrends } from '../../features/trend/hooks/useRelatedTrends';
import { useResurgingTrends } from '../../features/trend/hooks/useResurgingTrends';
import { useTopTrends } from '../../features/trend/hooks/useTopTrends';
import type { Trend, TrendFilterParams } from '../../features/trend/types/trend';

const ALL = '전체';
const categories = ['패션', '개발'];
const periods = [
  { value: '24h', label: '최근 24시간' },
  { value: '7d', label: '최근 7일' },
  { value: '30d', label: '최근 30일' },
];
/** 어느 목록을 볼지 고릅니다. 세 갈래가 각각 다른 API에서 옵니다. */
const statuses = [
  { value: 'all', label: '전체' },
  { value: 'top', label: '급상승' },
  { value: 'new', label: '신규' },
  { value: 'rising', label: '재급상승' },
];
const sorts = [
  { value: 'growth', label: '급상승순' },
  { value: 'mentions', label: '언급량순' },
];
const pageSizes = [6, 12, 24];
const relatedKeywordSets: Record<string, string[]> = {
  패션: ['아카이브 패션', '스웨이드 텍스처', '발레 플랫', '리워크 데님', '퍼스널 스타일', '유틸리티 웨어', '빈티지 셀렉션'],
  개발: ['사내 규칙 학습', 'PR 리뷰 대기시간', '리뷰 SLA', '코드 컨벤션 자동화', '리뷰 자동화 비용', '온디바이스 추론', '오픈모델 라이선스'],
};
/* 태그마다 색을 달리 해 카드가 한눈에 구분됩니다. 이름을 자릿수로 접어 고르므로 늘 같은 색이 나옵니다. */
const tagTones = ['indigo', 'rose', 'emerald', 'violet', 'amber'] as const;

function toneOf(label: string) {
  const sum = Array.from(label).reduce((total, char) => total + char.charCodeAt(0), 0);
  return tagTones[sum % tagTones.length];
}

/** 12.4만처럼 짧게 읽히게 줄입니다. */
function formatCount(count: number) {
  if (count >= 10_000) return `${(count / 10_000).toFixed(1)}만`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}천`;
  return count.toLocaleString();
}

function formatGrowth(trend: Trend) {
  return `${trend.growthRate > 0 ? '+' : ''}${trend.growthRate}%`;
}

function formatChange(trend: Trend) {
  if (trend.change === 'NEW') return 'NEW';
  if (typeof trend.change !== 'number' || trend.change === 0) return '—';
  return `${trend.change > 0 ? '▲' : '▼'} ${Math.abs(trend.change)}`;
}

function ArrowIcon({ size = 14, color = 'currentColor', width = 2.5 }: { size?: number; color?: string; width?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function BoltIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" />
    </svg>
  );
}

function SearchIcon({ size = 16, color = '#4F46E5' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.35-4.35" />
    </svg>
  );
}

/** 상세로 가는 키워드 링크. 끌어서 담기를 계속 쓸 수 있게 핸들러를 붙여 둡니다. */
function TrendKeyword({ trend, className = '' }: { trend: Trend; className?: string }) {
  const location = useLocation();
  const collectHandlers = useCollectHandlers(trend);
  return (
    <Link className={`explore-keyword ${className}`} to={{ pathname: `/trends/${trend.trendId}`, search: location.search }} {...collectHandlers}>
      {trend.keyword}
    </Link>
  );
}

/** 시안의 '···' 자리에 담기 버튼이 섭니다. 카드에서 바로 저장 보드로 넣을 수 있어야 합니다. */
function BookmarkButton({ trend, small = false }: { trend: Trend; small?: boolean }) {
  const { isSaved, toggleSave } = useCollect();
  const saved = isSaved(trend.trendId);
  return (
    <button
      type="button"
      className={`explore-bookmark${small ? ' explore-bookmark--sm' : ''}${saved ? ' is-saved' : ''}`}
      title={saved ? '담기 취소' : '담기'}
      aria-label={`${trend.keyword} ${saved ? '담기 취소' : '담기'}`}
      aria-pressed={saved}
      onClick={(event) => { event.preventDefault(); toggleSave(trend); }}
    >
      <svg viewBox="0 0 13 16" width={small ? 11 : 13} height={small ? 14 : 16} fill={saved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
        <path d="M1.5 1.5h10v13l-5-3.6-5 3.6z" />
      </svg>
    </button>
  );
}

function TagChip({ label }: { label: string }) {
  return <span className={`explore-tag explore-tag--${toneOf(label)}`}>{label}</span>;
}

function FilterSelect({ label, value, options, onChange, disabled = false, title }: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange?: (value: string) => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <div className="explore-filter">
      <span className="explore-filter-label">{label}</span>
      <div className={`explore-select${disabled ? ' is-disabled' : ''}`} title={title}>
        <select value={value} disabled={disabled} aria-label={label} onChange={(event) => onChange?.(event.target.value)}>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
      </div>
    </div>
  );
}

/** 1쪽과 마지막 쪽은 늘 보이고, 현재 쪽 둘레만 이어 붙입니다. 사이는 …로 접습니다. */
function pageList(current: number, total: number) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const shown = [...pages].filter((page) => page >= 1 && page <= total).sort((a, b) => a - b);
  const out: (number | 'gap')[] = [];
  shown.forEach((page, index) => {
    if (index > 0 && page - shown[index - 1] > 1) out.push('gap');
    out.push(page);
  });
  return out;
}

function FeaturedTrend({ trend, related }: { trend: Trend; related: Trend[] }) {
  const location = useLocation();
  return (
    <article className="explore-featured">
      <div className="explore-featured-body">
        <div className="explore-featured-head">
          <span className="explore-featured-rank">1</span>
          <h2><TrendKeyword trend={trend} className="explore-keyword--lg" /></h2>
          <TagChip label={trend.tag ?? trend.category} />
          <BookmarkButton trend={trend} />
        </div>

        <p className="explore-featured-growth">{formatGrowth(trend)}</p>
        <p className="explore-featured-growth-label">
          언급량 증가
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
            <path d="M7 17l5-5 4 4 5-7" /><path d="M17 7h4v4" />
          </svg>
        </p>

        {trend.description && <p className="explore-featured-desc">{trend.description}</p>}

        <div className="explore-featured-stats">
          <div><span>언급량</span><strong>{formatCount(trend.mentionCount)}</strong></div>
          <div><span>순위 변동</span><strong>{formatChange(trend)}</strong></div>
        </div>
        <p className="explore-featured-meta">{trend.category}{trend.tag ? ` · ${trend.tag}` : ''}</p>
      </div>

      <div className="explore-featured-chart">
        <Sparkline trend={trend} width={400} height={100} color="#4F46E5" filled points={14} className="explore-chart-svg" />
        <span className="explore-chart-badge">최근 {formatCount(trend.mentionCount)}</span>
      </div>

      <div className="explore-featured-keywords">
        <span className="explore-featured-keywords-label">연관 키워드</span>
        {/* 관심 키워드 등록은 이 화면에서만 되는 기능이라, 칩 안에 + 버튼을 그대로 둡니다. */}
        {related.slice(0, 4).map((item) => (
          <span className="explore-chip" key={item.trendId}>
            <Link to={{ pathname: `/trends/${item.trendId}`, search: location.search }}>{item.keyword}</Link>
            <AddInterestKeywordButton keyword={item.keyword} trendId={item.trendId} />
          </span>
        ))}
        {related.length > 4 && <span className="explore-featured-more">+{related.length - 4}</span>}
        <Link className="explore-featured-detail" to={{ pathname: `/trends/${trend.trendId}`, search: location.search }}>
          자세히 보기 <ArrowIcon size={12} />
        </Link>
      </div>
    </article>
  );
}

function TrendMiniCard({ trend, rank }: { trend: Trend; rank: number }) {
  const tone = trend.change === 'NEW' ? 'violet' : toneOf(trend.keyword);
  return (
    <article className="explore-card">
      <div className="explore-card-head">
        <span className="explore-card-rank">{rank}</span>
        <TrendKeyword trend={trend} />
        <TagChip label={trend.tag ?? trend.category} />
        <BookmarkButton trend={trend} small />
      </div>
      <p className={`explore-card-delta explore-card-delta--${tone}`}>
        {trend.change === 'NEW' ? 'NEW' : formatGrowth(trend)}
      </p>
      <p className="explore-card-mentions">언급량 {formatCount(trend.mentionCount)}</p>
      <Sparkline trend={trend} width={120} height={32} color="#818cf8" className="explore-card-chart" />
    </article>
  );
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawCategory = searchParams.get('category');
  const category = rawCategory && categories.includes(rawCategory) ? rawCategory : ALL;
  const period = periods.some((item) => item.value === searchParams.get('period')) ? searchParams.get('period')! : '24h';
  const status = statuses.some((item) => item.value === searchParams.get('status')) ? searchParams.get('status')! : 'all';
  const sort = sorts.some((item) => item.value === searchParams.get('sort')) ? searchParams.get('sort')! : 'growth';
  const size = pageSizes.includes(Number(searchParams.get('size'))) ? Number(searchParams.get('size')) : 6;
  const query = searchParams.get('q') ?? '';
  const [draft, setDraft] = useState(query);

  // 카테고리가 '전체'면 분야를 빼고 부릅니다. API는 분야 없이도 묶어서 내려줍니다.
  const params: TrendFilterParams = useMemo(
    () => ({ category: category === ALL ? undefined : category, period }),
    [category, period],
  );
  const topQuery = useTopTrends(params);
  const newQuery = useNewTrends(params);
  const risingQuery = useResurgingTrends(params);
  const relatedQuery = useRelatedTrends(params);

  const updateParams = (updates: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined) next.delete(key);
      else next.set(key, value);
    });
    // 조건이 바뀌면 보던 쪽 번호는 의미가 없어집니다.
    if (!('page' in updates)) next.delete('page');
    setSearchParams(next);
  };

  const topTrends = useMemo(() => topQuery.data ?? [], [topQuery.data]);
  const newTrends = useMemo(() => newQuery.data ?? [], [newQuery.data]);
  const risingTrends = useMemo(() => risingQuery.data ?? [], [risingQuery.data]);
  const relatedTrends = relatedQuery.data ?? [];

  /* 상태 칸이 어느 API의 목록을 볼지 고릅니다. '전체'는 셋을 합쳐 보여 줍니다. */
  const sourceQueries = status === 'all'
    ? [topQuery, newQuery, risingQuery]
    : [{ top: topQuery, new: newQuery, rising: risingQuery }[status]!];

  const trends = useMemo(() => {
    const source = status === 'all'
      ? [...topTrends, ...newTrends, ...risingTrends]
      : { top: topTrends, new: newTrends, rising: risingTrends }[status] ?? [];
    // 분야를 합치면 같은 키워드가 겹칠 수 있습니다.
    const unique = [...new Map(source.map((trend) => [trend.trendId, trend])).values()];
    const needle = query.trim().toLowerCase();
    const found = needle ? unique.filter((trend) => trend.keyword.toLowerCase().includes(needle)) : unique;
    return [...found].sort((a, b) => (sort === 'mentions' ? b.mentionCount - a.mentionCount : b.growthRate - a.growthRate));
  }, [newTrends, query, risingTrends, sort, status, topTrends]);

  const loading = sourceQueries.some((item) => item.isLoading);
  const failed = sourceQueries.some((item) => item.isError);
  const retry = () => sourceQueries.forEach((item) => void item.refetch());

  const featured = trends[0];
  const rest = trends.slice(1);
  const totalPages = Math.max(1, Math.ceil(rest.length / size));
  const page = Math.min(Math.max(1, Number(searchParams.get('page')) || 1), totalPages);
  const pageItems = rest.slice((page - 1) * size, page * size);

  const quickTags = useMemo(() => {
    const fromApi = relatedTrends.map((trend) => trend.keyword);
    const fallback = category === ALL
      ? [...relatedKeywordSets.패션, ...relatedKeywordSets.개발]
      : relatedKeywordSets[category] ?? [];
    return [...new Set([...fromApi, ...fallback])].slice(0, 9);
  }, [category, relatedTrends]);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    updateParams({ q: draft.trim() || undefined });
  };

  const runQuickTag = (keyword: string) => {
    setDraft(keyword);
    updateParams({ q: keyword });
  };

  return (
    <div className="explore-page">
      <section className="explore-hero">
        <div>
          <p className="explore-hero-eyebrow">트렌드를 더 빠르게, 더 깊이</p>
          <h1>트렌드 탐색</h1>
          <p className="explore-hero-lead">다양한 카테고리와 기간별로 급상승하는 트렌드를 탐색해보세요.</p>
        </div>
        <div className="explore-hero-visual">
          <img src={heroWave} alt="" />
          <div className="explore-hero-note">
            <p>지금 이 순간에도<br />새로운 트렌드가 만들어지고 있어요.</p>
          </div>
        </div>
      </section>

      <section className="explore-searchbar">
        <form onSubmit={submitSearch} role="search">
          <SearchIcon size={20} color="#9ca3af" />
          <input
            type="text"
            value={draft}
            placeholder="궁금한 키워드를 검색해보세요. 예) AI, 데님, 브라우저"
            aria-label="키워드 검색"
            onChange={(event) => setDraft(event.target.value)}
          />
          {query && (
            <button type="button" className="explore-search-clear" onClick={() => { setDraft(''); updateParams({ q: undefined }); }}>
              지우기
            </button>
          )}
          <button type="submit" className="explore-search-go" aria-label="검색">
            <ArrowIcon size={16} color="#fff" />
          </button>
        </form>
      </section>

      <section className="explore-filters">
        <FilterSelect label="기간" value={period} options={periods} onChange={(value) => updateParams({ period: value })} />

        <div className="explore-filter">
          <span className="explore-filter-label">카테고리</span>
          <div className="explore-chips" role="group" aria-label="카테고리">
            {[ALL, ...categories].map((item) => (
              <button
                type="button"
                key={item}
                className={`explore-cat${item === category ? ' is-selected' : ''}`}
                aria-pressed={item === category}
                onClick={() => updateParams({ category: item === ALL ? undefined : item })}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="explore-filters-right">
          {/* 플랫폼별 집계는 아직 API에 없습니다. 자리만 두고 잠가 둡니다. */}
          <FilterSelect label="플랫폼" value="all" options={[{ value: 'all', label: '전체' }]} disabled title="준비 중입니다" />
          <FilterSelect label="정렬" value={sort} options={sorts} onChange={(value) => updateParams({ sort: value })} />
          <FilterSelect label="상태" value={status} options={statuses} onChange={(value) => updateParams({ status: value })} />
        </div>
      </section>

      <section className="explore-main">
        {loading && <div className="explore-state" aria-label="불러오는 중"><span /><span /><span /></div>}
        {!loading && failed && (
          <div className="explore-state is-error" role="alert">
            <p>트렌드를 불러오지 못했습니다.</p>
            <button type="button" onClick={retry}>다시 시도</button>
          </div>
        )}
        {!loading && !failed && !featured && (
          <div className="explore-state" role="status">
            <p>{query ? `‘${query}’와 맞는 트렌드가 없습니다.` : '조건에 맞는 트렌드가 없습니다.'}</p>
          </div>
        )}

        {!loading && !failed && featured && (
          <div className="explore-grid">
            <FeaturedTrend trend={featured} related={relatedTrends} />

            <div className="explore-cards">
              {pageItems.map((trend, index) => (
                <TrendMiniCard key={trend.trendId} trend={trend} rank={(page - 1) * size + index + 2} />
              ))}
            </div>

            <aside className="explore-side">
              <div className="explore-panel">
                <div className="explore-panel-head"><BoltIcon /><span>실시간 인기 필터</span></div>
                <p className="explore-panel-lead">지금 뜨는 키워드로 빠르게 탐색해보세요.</p>
                {topTrends.slice(0, 5).map((trend, index) => (
                  <div className="explore-popular" key={trend.trendId}>
                    <span className="explore-popular-rank">{index + 1}</span>
                    <TrendKeyword trend={trend} />
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M7 17l5-5-5-5" /></svg>
                  </div>
                ))}
              </div>

              <div className="explore-panel">
                <div className="explore-panel-head"><SearchIcon /><span>빠른 탐색</span></div>
                <p className="explore-panel-lead">관심 있는 주제로 바로 이동해보세요.</p>
                <div className="explore-quick">
                  {quickTags.map((keyword) => (
                    <button type="button" key={keyword} onClick={() => runQuickTag(keyword)}>{keyword}</button>
                  ))}
                </div>
              </div>

              <Link className="explore-cta" to="/mypage">
                <span className="explore-cta-glow" />
                <p><BoltIcon /> 지금, 당신만의<br />관심 키워드를 등록해보세요.</p>
                <ArrowIcon size={14} color="#4338ca" />
              </Link>
            </aside>
          </div>
        )}
      </section>

      {!loading && !failed && featured && (
        <section className="explore-pagination">
          <span className="explore-total">총 <strong>{trends.length}</strong>개의 트렌드</span>

          <div className="explore-pages">
            <button type="button" disabled={page <= 1} aria-label="이전 쪽" onClick={() => updateParams({ page: String(page - 1) })}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
            </button>
            {pageList(page, totalPages).map((item, index) => (item === 'gap'
              ? <span className="explore-page-gap" key={`gap-${index}`}>···</span>
              : (
                <button
                  type="button"
                  key={item}
                  className={item === page ? 'is-current' : ''}
                  aria-current={item === page ? 'page' : undefined}
                  onClick={() => updateParams({ page: String(item) })}
                >
                  {item}
                </button>
              )))}
            <button type="button" disabled={page >= totalPages} aria-label="다음 쪽" onClick={() => updateParams({ page: String(page + 1) })}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M9 18l6-6-6-6" /></svg>
            </button>
          </div>

          <div className="explore-select">
            <select value={String(size)} aria-label="한 쪽에 보여 줄 개수" onChange={(event) => updateParams({ size: event.target.value })}>
              {pageSizes.map((option) => <option key={option} value={option}>{option}개씩 보기</option>)}
            </select>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
          </div>
        </section>
      )}
    </div>
  );
}
