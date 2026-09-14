import { useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import heroWave from '../../assets/flowing-wave.webp';
import { useNewTrends } from '../../features/trend/hooks/useNewTrends';
import { useResurgingTrends } from '../../features/trend/hooks/useResurgingTrends';
import { useTopTrends } from '../../features/trend/hooks/useTopTrends';
import type { Trend } from '../../features/trend/types/trend';
import { LandingHeader } from './LandingHeader';
import { landingContents } from './landingContents';

type BoardTone = 'rising' | 'new' | 'resurging';

interface TrendBoardProps {
  title: string;
  tone: BoardTone;
  trends: Trend[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}

function ArrowIcon({ size = 14, color = '#374151', width = 2 }: { size?: number; color?: string; width?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function formatGrowth(trend: Trend) {
  return `${trend.growthRate > 0 ? '+' : ''}${trend.growthRate}%`;
}

/** 히어로의 언급량 배지는 자리가 좁아 짧게 줄입니다. 10만 건이 '0.1M'으로 보이면 안 됩니다. */
function formatCompact(count: number) {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${Math.round(count / 1_000).toLocaleString()}K`;
  return count.toLocaleString();
}

/** 시안의 카드 한 장. 머리쪽 그라데이션은 톤별로 CSS가 들고 있습니다. */
function TrendBoard({ title, tone, trends, loading, error, onRetry }: TrendBoardProps) {
  const rows = trends.slice(0, 3);

  return (
    <article className="landing-board">
      <div className={`landing-board-cover landing-board-cover--${tone}`}>
        <span className="landing-board-blob landing-board-blob--a" />
        <span className="landing-board-blob landing-board-blob--b" />
        <Link className="landing-board-more" to="/dashboard" aria-label={`${title} 전체 보기`}>
          <ArrowIcon />
        </Link>
      </div>
      <div className="landing-board-body">
        <h3>{title}</h3>
        {loading && <p className="landing-board-note">불러오는 중…</p>}
        {!loading && error && (
          <p className="landing-board-note">
            불러오지 못했습니다.{' '}
            <button type="button" onClick={onRetry}>다시 시도</button>
          </p>
        )}
        {!loading && !error && rows.length === 0 && <p className="landing-board-note">아직 집계된 키워드가 없습니다.</p>}
        {!loading && !error && rows.map((trend, index) => (
          <div className="landing-board-row" key={trend.trendId}>
            <span className="landing-board-rank">{index + 1}</span>
            <Link className="landing-board-keyword" to={`/trends/${trend.trendId}`}>{trend.keyword}</Link>
            {tone === 'new'
              ? <span className="landing-board-badge">NEW</span>
              : <span className="landing-board-delta">{formatGrowth(trend)}</span>}
          </div>
        ))}
      </div>
    </article>
  );
}

/** 시안의 09.01~09.07 축을 오늘 기준 최근 이레로 바꿔 둡니다. */
function recentDays(count = 7) {
  const today = new Date();
  return Array.from({ length: count }, (_, index) => {
    const day = new Date(today);
    day.setDate(today.getDate() - (count - 1 - index));
    return `${String(day.getMonth() + 1).padStart(2, '0')}.${String(day.getDate()).padStart(2, '0')}`;
  });
}

export function LandingPage() {
  const navigate = useNavigate();
  const topQuery = useTopTrends();
  const newQuery = useNewTrends();
  const resurgingQuery = useResurgingTrends();

  const [keyword, setKeyword] = useState('');
  const [searchMiss, setSearchMiss] = useState<string>();

  const topTrends = useMemo(() => topQuery.data ?? [], [topQuery.data]);

  // 검색 화면이 아직 없어서, 이미 받아 둔 세 목록 안에서 찾아 상세로 보냅니다.
  const searchPool = useMemo(
    () => [...topTrends, ...(newQuery.data ?? []), ...(resurgingQuery.data ?? [])],
    [topTrends, newQuery.data, resurgingQuery.data],
  );

  const goToKeyword = (value: string) => {
    const query = value.trim();
    if (!query) return;
    const hit = searchPool.find((trend) => trend.keyword.toLowerCase().includes(query.toLowerCase()));
    if (!hit) {
      setSearchMiss(query);
      return;
    }
    setSearchMiss(undefined);
    navigate(`/trends/${hit.trendId}`);
  };

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    goToKeyword(keyword);
  };

  const hotTags = topTrends.slice(0, 5);
  const totalMentions = topTrends.reduce((sum, trend) => sum + trend.mentionCount, 0);
  const headlineGrowth = topTrends[0] ? formatGrowth(topTrends[0]) : null;
  const axis = recentDays();

  return (
    <div className="landing-page">
      <LandingHeader />

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="landing-eyebrow">REAL-TIME TREND INSIGHTS</p>
          <h1>지금,<br />세상을 움직이는<br /><span>트렌드</span>를 담다</h1>
          <p className="landing-hero-lead">수많은 데이터 속에서 중요한 흐름을 찾아,<br />더 빠르고, 더 깊이 있게.</p>

          <form className="landing-search" onSubmit={submitSearch} role="search">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              type="text"
              value={keyword}
              placeholder="관심 있는 키워드를 검색해보세요."
              aria-label="키워드 검색"
              onChange={(event) => { setKeyword(event.target.value); setSearchMiss(undefined); }}
            />
            <button type="submit" aria-label="검색">
              <ArrowIcon size={16} color="#fff" width={2.5} />
            </button>
          </form>
          {searchMiss && <p className="landing-search-miss" role="status">‘{searchMiss}’와 맞는 트렌드를 찾지 못했습니다.</p>}

          <div className="landing-tags">
            <span className="landing-tags-label">🔥 실시간 인기</span>
            {hotTags.map((trend) => (
              <Link className="landing-tag" key={trend.trendId} to={`/trends/${trend.trendId}`}>{trend.keyword}</Link>
            ))}
            <Link className="landing-tag landing-tag--more" to="/dashboard" aria-label="트렌드 전체 보기">···</Link>
          </div>
        </div>

        <div className="landing-hero-visual">
          <div className="landing-hero-wave">
            <img src={heroWave} alt="" />
          </div>
          <div className="landing-float landing-float--growth">
            <p className="landing-float-value">{headlineGrowth ?? '—'}</p>
            <p className="landing-float-label">언급량 증가</p>
          </div>
          <div className="landing-float landing-float--volume">
            <p className="landing-float-value">{totalMentions ? formatCompact(totalMentions) : '—'}</p>
            <p className="landing-float-label">실시간 언급량</p>
          </div>
          <div className="landing-float landing-float--note">
            <p>지금, 새로운<br />트렌드가 계속 생겨나고 있어요.</p>
          </div>
          <p className="landing-hero-side">DISCOVER<br />ANALYZE<br />BE INSPIRED</p>
        </div>
      </section>

      <div className="landing-divider" />

      <section className="landing-section">
        <div className="landing-section-head">
          <div>
            <h2>오늘의 트렌드</h2>
            <p>지금 가장 주목받는 키워드를 한눈에 확인해보세요.</p>
          </div>
          <Link className="landing-section-more" to="/dashboard">전체 보기 <span aria-hidden="true">→</span></Link>
        </div>

        <div className="landing-boards">
          <TrendBoard
            title="급상승 트렌드"
            tone="rising"
            trends={topTrends}
            loading={topQuery.isLoading}
            error={topQuery.isError}
            onRetry={() => void topQuery.refetch()}
          />
          <TrendBoard
            title="신규 트렌드"
            tone="new"
            trends={newQuery.data ?? []}
            loading={newQuery.isLoading}
            error={newQuery.isError}
            onRetry={() => void newQuery.refetch()}
          />
          <TrendBoard
            title="재급상승 트렌드"
            tone="resurging"
            trends={resurgingQuery.data ?? []}
            loading={resurgingQuery.isLoading}
            error={resurgingQuery.isError}
            onRetry={() => void resurgingQuery.refetch()}
          />
        </div>
      </section>

      <section className="landing-beyond">
        <div className="landing-beyond-inner">
          <div>
            <p className="landing-eyebrow landing-eyebrow--wide">BEYOND KEYWORDS</p>
            <h2>트렌드는<br />데이터로 더 명확해집니다.</h2>
            <p className="landing-beyond-lead">실시간 언급량과 주요 흐름을 분석해,<br />지금 이슈가 되는 이유를 보여드려요.</p>
            <Link className="landing-btn landing-btn--dark landing-beyond-cta" to="/dashboard">
              트렌드 더 알아보기 <ArrowIcon size={14} color="currentColor" width={2.5} />
            </Link>
          </div>

          <div className="landing-chart-wrap">
            <span className="landing-chart-glow" />
            <div className="landing-chart-card">
              <div className="landing-chart-head">
                <span>전체 트렌드 언급량</span>
                <span className="landing-chart-scope">전체 ▾</span>
              </div>
              <div className="landing-chart-figure">
                <strong>{totalMentions ? totalMentions.toLocaleString() : '—'}</strong>
                {headlineGrowth && <span>{headlineGrowth}</span>}
              </div>
              <svg viewBox="0 0 480 140" width="100%" height="140" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                  <linearGradient id="landingChartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4F46E5" stopOpacity="0.15" />
                    <stop offset="100%" stopColor="#4F46E5" stopOpacity="0" />
                  </linearGradient>
                </defs>
                <path d="M0,120 C40,115 80,110 120,100 C160,90 180,95 220,80 C260,65 280,70 320,45 C360,20 400,35 440,15 C460,8 475,5 480,4 L480,140 L0,140 Z" fill="url(#landingChartGrad)" />
                <path d="M0,120 C40,115 80,110 120,100 C160,90 180,95 220,80 C260,65 280,70 320,45 C360,20 400,35 440,15 C460,8 475,5 480,4" fill="none" stroke="#4F46E5" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="320" cy="45" r="4" fill="#fff" stroke="#4F46E5" strokeWidth="2" />
              </svg>
              <div className="landing-chart-axis">
                {axis.map((label) => <span key={label}>{label}</span>)}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-section">
        <div className="landing-section-head">
          <div>
            <h2>지금 주목할 만한 콘텐츠</h2>
            <p>트렌드와 관련된 주요 콘텐츠를 모았습니다.</p>
          </div>
          <Link className="landing-section-more" to="/dashboard">전체 보기 <span aria-hidden="true">→</span></Link>
        </div>

        <div className="landing-contents">
          {landingContents.map((content) => (
            <article className="landing-content" key={content.id}>
              <div className="landing-content-cover" style={{ background: content.background }} />
              <div className="landing-content-body">
                <h4>{content.title}</h4>
                <p className="landing-content-desc">{content.description}</p>
                <p className="landing-content-meta">{content.source} · {content.time}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="landing-footer-brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#9ca3af" />
            </svg>
            <span>TrendIn</span>
          </div>
          <p>© {new Date().getFullYear()} TrendIn. 실시간 트렌드 분석 플랫폼</p>
        </div>
      </footer>
    </div>
  );
}
