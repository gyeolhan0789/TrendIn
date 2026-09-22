import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import { SiteFooter } from '../../components/layout/SiteFooter';
import { FeaturedContentsCarousel } from './components/FeaturedContentsCarousel';
import { ParticleWave } from './components/ParticleWave';
import { TodayTrends } from './components/TodayTrends';
import { TrendSearch } from './components/TrendSearch';
import {
  claimFirstLandingAnimationSafely,
  claimFirstLandingGuideSafely,
} from '../../utils/landingExperience';
import { useLandingDomain } from './useLandingDomain';
import './particleLanding.css';

export function LandingPage() {
  const version: string = '3';
  const isDark = version === '2' || version === '3';
  const session = useAuthSession();
  const [playEntryAnimation] = useState(claimFirstLandingAnimationSafely);
  const [waveReady, setWaveReady] = useState(!playEntryAnimation);
  const [showGuide, setShowGuide] = useState(() => Boolean(session) && claimFirstLandingGuideSafely());
  const trendsDomain = useLandingDomain();
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
            <TodayTrends {...trendsDomain} />
            {version === '3' && <section className="featured-section" aria-labelledby="featured-title">
              <div className="section-heading">
                <div><h2 id="featured-title">지금 주목할 만한 콘텐츠</h2><p>가을 패션에서 주목할 만한 콘텐츠를 모았습니다.</p></div>
              </div>
              <FeaturedContentsCarousel />
            </section>}
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
