import { useCallback, useEffect, useRef, useState } from 'react';
import { ParticleWave } from './components/ParticleWave';
import { TrendSearch } from './components/TrendSearch';
import './particleLanding.css';

const boards = [
  { title: '급상승 트렌드', tone: 'rising', rows: [['01', '발레코어', '+128%'], ['02', '스웨이드 백', '+84%'], ['03', '레트로 스니커즈', '+62%']] },
  { title: '신규 트렌드', tone: 'new', rows: [['01', '레이스 레이어링', 'NEW'], ['02', '버터 옐로', 'NEW'], ['03', '스카프 스타일링', 'NEW']] },
  { title: '재급상승 트렌드', tone: 'returning', rows: [['01', '시어 소재', '+76%'], ['02', '메리제인 슈즈', '+51%'], ['03', '와이드 데님', '+39%']] },
];

const featuredContents = [
  { title: '발레코어, 일상에 스며든 로맨틱한 실루엣', description: '리본과 플랫 슈즈로 완성하는 가벼운 스타일링', source: 'Style Edit', time: '2시간 전', tag: '스타일링' },
  { title: '스웨이드 백으로 시작하는 가을', description: '부드러운 질감과 브라운 톤의 새로운 조합', source: 'Fashion Notes', time: '3시간 전', tag: '액세서리' },
  { title: '레트로 스니커즈가 돌아왔다', description: '세계의 스트리트에서 찾은 빈티지한 매력', source: 'Street Journal', time: '5시간 전', tag: '스트리트' },
  { title: '버터 옐로, 옷장에 더하는 한 끗', description: '니트부터 스카프까지, 은은한 컬러 포인트', source: 'Palette', time: '6시간 전', tag: '컬러' },
];

export function LandingPage() {
  const version: string = '3';
  const isDark = version === '2' || version === '3';
  const [waveReady, setWaveReady] = useState(false);
  const onWaveReady = useCallback(() => setWaveReady(true), []);
  const pageRef = useRef<HTMLDivElement>(null);
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
          <ParticleWave variant={version === '3' ? 'transition' : isDark ? 'dark' : 'light'} onEntryComplete={onWaveReady} />
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
                {featuredContents.map((content) => <article className="featured-card" key={content.title}>
                  <span className="featured-tag">{content.tag}</span>
                  <div><h3>{content.title}</h3><p>{content.description}</p></div>
                  <span className="featured-meta">{content.source} · {content.time}</span>
                </article>)}
              </div>
            </section>}
          </div>
        </section>
      </main>
      <footer className="site-footer"><span>trend<span>in</span></span><span>{version === '3' ? '@SSAFY_A102' : '흐름을 읽는 새로운 시선'}</span></footer>
    </div>
  );
}
