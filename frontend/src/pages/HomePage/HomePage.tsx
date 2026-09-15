import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import heroWave from '../../assets/flowing-wave.webp';
import { AddInterestKeywordButton } from '../../features/myPage/components/AddInterestKeywordButton';
import { BookmarkButton } from '../../features/savedTrend/components/BookmarkButton';
import { useDomains } from '../../features/onboarding/hooks/useDomains';
import { TrendSparkline } from '../../features/trend/components/TrendSparkline';
import { useTrendHistory } from '../../features/trend/hooks/useTrendHistory';
import { useTrendRelatedKeywords } from '../../features/trend/hooks/useTrendRelatedKeywords';
import { useTrends } from '../../features/trend/hooks/useTrends';
import { ANALYSIS_PERIODS, parsePeriod, resolveDomainCode } from '../../constants/filterCodes';
import type { PeriodCode } from '../../constants/filterCodes';
import { TREND_TYPES } from '../../features/trend/types/trend';
import type { Trend, TrendAnalysisWindow, TrendType } from '../../features/trend/types/trend';

const periodLabels: Record<PeriodCode, string> = {
  '24H': '최근 24시간',
  '7D': '최근 7일',
  '30D': '최근 30일',
};

/** 서버가 가르는 세 갈래. 시안의 '상태' 칸이 이 값을 고릅니다. */
const typeLabels: Record<TrendType, string> = {
  CURRENT: '급상승',
  NEW: '신규',
  RISING: '재급상승',
};

const sorts = [
  { value: 'rank', label: '순위순' },
  { value: 'growth', label: '급상승순' },
  { value: 'mentions', label: '언급량순' },
];
const pageSizes = [6, 12, 24];
/** 시안의 큰 카드가 목록의 첫 자리를 가져가고, 나머지가 카드 격자로 갑니다. */
const FEATURED_COUNT = 1;

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

/** 이전 구간 언급량이 없으면 서버가 증가율을 비워 둡니다. 그 자리에 숫자를 지어내지 않습니다. */
function formatGrowth(trend: Trend) {
  if (trend.growthRate === null) return '—';
  return `${trend.growthRate > 0 ? '+' : ''}${trend.growthRate}%`;
}

function formatWindowDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[2]}.${match[3]}` : value;
}

function describeWindow(window: TrendAnalysisWindow | null | undefined) {
  if (!window) return undefined;
  return `${formatWindowDate(window.recentStart)} ~ ${formatWindowDate(window.recentEnd)} 집계 · 직전 구간과 비교`;
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

function TagChip({ label }: { label: string }) {
  return <span className={`explore-tag explore-tag--${toneOf(label)}`}>{label}</span>;
}

function TrendKeyword({ trend, className = '' }: { trend: Trend; className?: string }) {
  return <Link className={`explore-keyword ${className}`} to={`/trends/${trend.trendId}`}>{trend.keyword}</Link>;
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

function FeaturedTrend({ trend, period }: { trend: Trend; period: PeriodCode }) {
  const historyQuery = useTrendHistory(trend.trendId, period);
  const relatedQuery = useTrendRelatedKeywords(trend.trendId);
  const history = historyQuery.data?.history ?? [];
  const related = relatedQuery.data ?? [];

  return (
    <article className="explore-featured">
      <div className="explore-featured-body">
        <div className="explore-featured-head">
          <span className="explore-featured-rank">{trend.rank ?? 1}</span>
          <h2><TrendKeyword trend={trend} className="explore-keyword--lg" /></h2>
          <TagChip label={trend.domain.name} />
          <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="explore-bookmark" />
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
          <div><span>직전 구간</span><strong>{formatCount(trend.previousMentionCount)}</strong></div>
          <div><span>증가량</span><strong>{trend.growthAmount > 0 ? '+' : ''}{formatCount(trend.growthAmount)}</strong></div>
        </div>
        <p className="explore-featured-meta">{trend.domain.name} · {trend.trendTypes.map((item) => typeLabels[item]).join(' · ')}</p>
      </div>

      <div className="explore-featured-chart">
        {/* 큰 카드만 이력을 따로 불러옵니다. 카드마다 부르면 한 쪽에 수십 번이 됩니다. */}
        {history.length > 0
          ? (
            <TrendSparkline
              points={history.map((point) => point.mentionCount)}
              width={400}
              height={100}
              color="#4F46E5"
              filled
              gradientId={`explore-featured-${trend.trendId}`}
              className="explore-chart-svg"
            />
          )
          : <p className="explore-chart-empty">{historyQuery.isLoading ? '추이를 불러오는 중…' : '표시할 추이가 없습니다.'}</p>}
        {history.length > 0 && <span className="explore-chart-badge">최근 {formatCount(trend.mentionCount)}</span>}
      </div>

      <div className="explore-featured-keywords">
        <span className="explore-featured-keywords-label">연관 키워드</span>
        {related.slice(0, 4).map((item) => (
          <span className="explore-chip" key={item.keywordId}>
            <span>{item.keyword}</span>
            <AddInterestKeywordButton keywordId={item.keywordId} keyword={item.keyword} />
          </span>
        ))}
        {related.length > 4 && <span className="explore-featured-more">+{related.length - 4}</span>}
        <Link className="explore-featured-detail" to={`/trends/${trend.trendId}`}>
          자세히 보기 <ArrowIcon size={12} />
        </Link>
      </div>
    </article>
  );
}

function TrendMiniCard({ trend, rank }: { trend: Trend; rank: number }) {
  const isNew = trend.trendTypes.includes('NEW');
  const tone = isNew ? 'violet' : toneOf(trend.keyword);
  return (
    <article className="explore-card">
      <div className="explore-card-head">
        <span className="explore-card-rank">{rank}</span>
        <TrendKeyword trend={trend} />
        <TagChip label={trend.domain.name} />
        <BookmarkButton trendId={trend.trendId} keyword={trend.keyword} className="explore-bookmark explore-bookmark--sm" />
      </div>
      <p className={`explore-card-delta explore-card-delta--${tone}`}>
        {isNew && trend.growthRate === null ? 'NEW' : formatGrowth(trend)}
      </p>
      <p className="explore-card-mentions">언급량 {formatCount(trend.mentionCount)}</p>
      {/* 카드마다 이력을 부를 수 없어, 이미 받은 직전 구간과 현재 두 값으로 방향만 보여 줍니다. */}
      <TrendSparkline
        points={[trend.previousMentionCount, trend.mentionCount]}
        width={120}
        height={32}
        color={trend.growthAmount < 0 ? '#f87171' : '#818cf8'}
        className="explore-card-chart"
      />
    </article>
  );
}

export function HomePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const domainsQuery = useDomains();
  const domains = useMemo(() => domainsQuery.data ?? [], [domainsQuery.data]);

  const period = parsePeriod(searchParams.get('period'));
  const rawType = searchParams.get('status')?.toUpperCase() ?? '';
  const type: TrendType = (TREND_TYPES as readonly string[]).includes(rawType) ? (rawType as TrendType) : 'CURRENT';
  const sort = sorts.some((item) => item.value === searchParams.get('sort')) ? searchParams.get('sort')! : 'rank';
  const size = pageSizes.includes(Number(searchParams.get('size'))) ? Number(searchParams.get('size')) : 6;
  const query = searchParams.get('q') ?? '';
  const [draft, setDraft] = useState(query);

  // 분야 목록을 받기 전에는 고를 분야가 없어 조회를 멈춰 둡니다.
  const domain = resolveDomainCode(searchParams.get('category'), domains);
  const pageFromUrl = Math.max(1, Number(searchParams.get('page')) || 1);
  /* 서버 쪽 번호는 0부터입니다. 큰 카드가 한 자리를 쓰므로 그만큼 더 받아야 격자가 찹니다. */
  const listQuery = useTrends(domain
    ? { domain, type, period, page: pageFromUrl - 1, size: size + FEATURED_COUNT }
    : undefined);

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

  const trends = useMemo(() => {
    const received = listQuery.data?.trends ?? [];
    const needle = query.trim().toLowerCase();
    // 검색은 받아 온 쪽 안에서만 걸러 줍니다. 전체 검색은 별도 화면이 생기면 그리로 옮깁니다.
    const found = needle ? received.filter((trend) => trend.keyword.toLowerCase().includes(needle)) : received;
    if (sort === 'rank') return found;
    return [...found].sort((a, b) => (sort === 'mentions'
      ? b.mentionCount - a.mentionCount
      : (b.growthRate ?? -Infinity) - (a.growthRate ?? -Infinity)));
  }, [listQuery.data, query, sort]);

  const loading = domainsQuery.isLoading || listQuery.isLoading;
  const failed = domainsQuery.isError || listQuery.isError;
  const retry = () => {
    if (domainsQuery.isError) void domainsQuery.refetch();
    if (listQuery.isError) void listQuery.refetch();
  };

  const featured = trends[0];
  const rest = trends.slice(FEATURED_COUNT);
  const hasNext = listQuery.data?.hasNext ?? false;
  // 서버가 전체 개수를 주지 않아, 지금 쪽과 다음 쪽 유무만으로 쪽 번호를 만듭니다.
  const totalPages = hasNext ? pageFromUrl + 1 : pageFromUrl;
  const windowLabel = describeWindow(listQuery.data?.analysisWindow);

  const quickTags = useMemo(() => trends.slice(0, 9).map((trend) => trend.keyword), [trends]);

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
          <p className="explore-hero-lead">{windowLabel ?? '다양한 카테고리와 기간별로 급상승하는 트렌드를 탐색해보세요.'}</p>
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
            placeholder="이 목록에서 키워드를 찾아보세요."
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
        <FilterSelect
          label="기간"
          value={period}
          options={ANALYSIS_PERIODS.map((code) => ({ value: code, label: periodLabels[code] }))}
          onChange={(value) => updateParams({ period: value })}
        />

        <div className="explore-filter">
          <span className="explore-filter-label">카테고리</span>
          <div className="explore-chips" role="group" aria-label="카테고리">
            {domains.map((option) => (
              <button
                type="button"
                key={option.domain}
                className={`explore-cat${option.domain === domain ? ' is-selected' : ''}`}
                aria-pressed={option.domain === domain}
                onClick={() => updateParams({ category: option.domain })}
              >
                {option.name}
              </button>
            ))}
            {domains.length === 0 && <span className="explore-filter-label">분야를 불러오는 중…</span>}
          </div>
        </div>

        <div className="explore-filters-right">
          {/* 플랫폼별 집계는 아직 API에 없습니다. 자리만 두고 잠가 둡니다. */}
          <FilterSelect label="플랫폼" value="all" options={[{ value: 'all', label: '전체' }]} disabled title="준비 중입니다" />
          <FilterSelect label="정렬" value={sort} options={sorts} onChange={(value) => updateParams({ sort: value })} />
          <FilterSelect
            label="상태"
            value={type}
            options={TREND_TYPES.map((code) => ({ value: code, label: typeLabels[code] }))}
            onChange={(value) => updateParams({ status: value })}
          />
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
            <p>{query ? `‘${query}’와 맞는 트렌드가 이 쪽에 없습니다.` : '조건에 맞는 트렌드가 없습니다.'}</p>
          </div>
        )}

        {!loading && !failed && featured && (
          <div className="explore-grid">
            <FeaturedTrend trend={featured} period={period} />

            <div className="explore-cards">
              {rest.map((trend, index) => (
                <TrendMiniCard key={trend.trendId} trend={trend} rank={trend.rank ?? index + 2} />
              ))}
            </div>

            <aside className="explore-side">
              <div className="explore-panel">
                <div className="explore-panel-head"><BoltIcon /><span>실시간 인기 필터</span></div>
                <p className="explore-panel-lead">지금 뜨는 키워드로 빠르게 탐색해보세요.</p>
                {trends.slice(0, 5).map((trend, index) => (
                  <div className="explore-popular" key={trend.trendId}>
                    <span className="explore-popular-rank">{trend.rank ?? index + 1}</span>
                    <TrendKeyword trend={trend} />
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#c4b5fd" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M7 17l5-5-5-5" /></svg>
                  </div>
                ))}
              </div>

              <div className="explore-panel">
                <div className="explore-panel-head"><SearchIcon /><span>빠른 탐색</span></div>
                <p className="explore-panel-lead">이 목록에서 키워드로 바로 걸러 보세요.</p>
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
          <span className="explore-total">{pageFromUrl}쪽 · <strong>{trends.length}</strong>개 보는 중</span>

          <div className="explore-pages">
            <button type="button" disabled={pageFromUrl <= 1} aria-label="이전 쪽" onClick={() => updateParams({ page: String(pageFromUrl - 1) })}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true"><path d="M15 18l-6-6 6-6" /></svg>
            </button>
            {pageList(pageFromUrl, totalPages).map((item, index) => (item === 'gap'
              ? <span className="explore-page-gap" key={`gap-${index}`}>···</span>
              : (
                <button
                  type="button"
                  key={item}
                  className={item === pageFromUrl ? 'is-current' : ''}
                  aria-current={item === pageFromUrl ? 'page' : undefined}
                  onClick={() => updateParams({ page: String(item) })}
                >
                  {item}
                </button>
              )))}
            <button type="button" disabled={!hasNext} aria-label="다음 쪽" onClick={() => updateParams({ page: String(pageFromUrl + 1) })}>
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
