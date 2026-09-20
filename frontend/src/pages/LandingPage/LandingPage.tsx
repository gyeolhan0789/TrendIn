import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import { useFeaturedTrendContents } from '../../features/trend/hooks/useFeaturedTrendContents';
import { SiteFooter } from '../../components/layout/SiteFooter';
import { ParticleWave } from './components/ParticleWave';
import { TrendSearch } from './components/TrendSearch';
import {
  claimFirstLandingAnimationSafely,
  claimFirstLandingGuideSafely,
} from '../../utils/landingExperience';
import './particleLanding.css';

const boards = [
  { title: '급상승 트렌드', tone: 'rising', rows: [['01', '발레코어', '+128%'], ['02', '스웨이드 백', '+84%'], ['03', '레트로 스니커즈', '+62%']] },
  { title: '신규 트렌드', tone: 'new', rows: [['01', '레이스 레이어링', 'NEW'], ['02', '버터 옐로', 'NEW'], ['03', '스카프 스타일링', 'NEW']] },
  { title: '재급상승 트렌드', tone: 'returning', rows: [['01', '시어 소재', '+76%'], ['02', '메리제인 슈즈', '+51%'], ['03', '와이드 데님', '+39%']] },
];

function formatPublishedAt(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('ko-KR', { month: 'short', day: 'numeric' }).format(date);
}

export function LandingPage() {
  const version: string = '3';
  const isDark = version === '2' || version === '3';
  const session = useAuthSession();
  const [playEntryAnimation] = useState(claimFirstLandingAnimationSafely);
  const [waveReady, setWaveReady] = useState(!playEntryAnimation);
  const [showGuide, setShowGuide] = useState(() => Boolean(session) && claimFirstLandingGuideSafely());
  const featuredQuery = useFeaturedTrendContents();
  const onWaveReady = useCallback(() => setWaveReady(true), []);
  const pageRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showGuide) return;
    const timeout = window.setTimeout(() => setShowGuide(false), 3000);
    return () => window.clearTimeout(timeout);
  }, [showGuide]);
  useEffect(() => {
    if (version !== '3') return;
    const layout = pageRef.current?.parentElement;
    const updateBackground = () => {
      const page = pageRef.current;
      const hero = page?.querySelector('.hero');
      if (!page || !hero) return;
      const rect = hero.getBoundingClientRect();
      const progress = Math.min(1, Math.max(0, (-rect.top + 64) / rect.height));
      const eased = progress * progress * (3 - 2 * progress);
      page.style.setProperty('--scroll-light', `${eased * 100}%`);
      page.style.setProperty('--dark-opacity', `${1 - eased}`);
      layout?.style.setProperty('--home-header-light', `${eased * 100}%`);
      // The page's dark overlay also fades, so its visible white contribution is eased².
      layout?.style.setProperty('--home-header-background-light', `${eased * eased * 100}%`);
    };
    updateBackground();
    window.addEventListener('scroll', updateBackground, { passive: true });
    window.addEventListener('resize', updateBackground);
    return () => {
      window.removeEventListener('scroll', updateBackground);
      window.removeEventListener('resize', updateBackground);
      layout?.style.removeProperty('--home-header-light');
      layout?.style.removeProperty('--home-header-background-light');
    };
  }, [version]);
  return (
    <div ref={pageRef} className={`particle-landing${isDark ? ' demo-page--v2' : ''}${version === '3' ? ' demo-page--v3' : ''}`}>
<main>
        <section className="hero" id="top" aria-label="파티클 물결 인터랙션">
          <ParticleWave variant={version === '3' ? 'transition' : isDark ? 'dark' : 'light'} playEntryAnimation={playEntryAnimation} onEntryComplete={onWaveReady} />
          {showGuide && <div className="interaction-guide" role="status">
            <span aria-hidden="true">✦</span>
            <p>마우스로 흐름을 만들고,<br />드래그로 물결을 둘러보세요.</p>
          </div>}
          {version === '3' && <div className={`hero-search caption-after-wave${waveReady ? ' is-visible' : ''}`} inert={!waveReady} aria-hidden={!waveReady}>
            <TrendSearch />
          </div>}
          {isDark && <div className={`v2-caption${version === '3' ? ` caption-after-wave${waveReady ? ' is-visible' : ''}` : ''}`} aria-hidden={version === '3' && !waveReady}>{version !== '3' && <span>FLOW OF SIGNALS</span>}<h2>흐름 속에서,<br />새로운 신호를 발견하다.</h2>{version !== '3' && <p>마우스로 흐름을 만들고, 드래그로 물결을 돌려보세요.</p>}</div>}
        </section>

        <section className="trends-section" id="trends">
          <div className="trends-inner">
            <div className="section-heading">
              <div>
                <h1>오늘의 트렌드</h1>
                <p>지금 가장 주목받는 패션 키워드를 한눈에 확인해보세요.</p>
              </div>
              <span className="demo-badge">DEMO DATA</span>
            </div>
            <div className="trend-boards">
              {boards.map((board) => (
                <article className={`trend-board trend-board--${board.tone}`} key={board.title}>
                  {version !== '3' && <div className="trend-board-art" aria-hidden="true"><span /><span /></div>}
                  <div className="trend-board-body">
                    <h2>{version === '3' ? (board.tone === 'rising' ? '인기 트렌드' : board.tone === 'returning' ? '급상승 트렌드' : board.title) : board.title}</h2>
                    {board.rows.map(([rank, keyword, growth]) => (
                      <div className="trend-row" key={keyword}>
                        <span className="trend-rank">{rank}</span>
                        <span className="trend-keyword">{keyword}</span>
                        <span className={`trend-growth ${growth === 'NEW' ? 'trend-growth--new' : ''}`}>{growth}</span>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
            {version === '3' && <section className="featured-section" aria-labelledby="featured-title">
              <div className="section-heading">
                <div><h2 id="featured-title">지금 주목할 만한 콘텐츠</h2><p>패션 트렌드와 관련된 주요 콘텐츠를 모았습니다.</p></div>
              </div>
              <div className="featured-grid">
                {featuredQuery.data?.map(({ trend, content }) => <a className="featured-card" href={content.url} key={trend.trendId} target="_blank" rel="noreferrer">
                  <span className="featured-tag">인기 {trend.rank ?? '-' }위 · {trend.keyword}</span>
                  <div><h3>{content.title}</h3><p>{trend.description ?? `${trend.keyword} 트렌드의 대표 콘텐츠입니다.`}</p></div>
                  <span className="featured-meta">{content.source} · {formatPublishedAt(content.publishedAt)}</span>
                </a>)}
              </div>
              {featuredQuery.isPending && <p className="featured-state">콘텐츠를 불러오는 중입니다.</p>}
              {featuredQuery.isError && <div className="featured-state" role="alert">콘텐츠를 불러오지 못했습니다. <button type="button" onClick={() => void featuredQuery.refetch()}>다시 시도</button></div>}
              {!featuredQuery.isPending && !featuredQuery.isError && featuredQuery.data?.length === 0 && <p className="featured-state">아직 소개할 콘텐츠가 없습니다.</p>}
            </section>}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
