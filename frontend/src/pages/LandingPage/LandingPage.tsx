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
import { SCROLL_FOLLOW_EPSILON, followStep } from './scrollFollow';
import { useSectionGlide } from './useSectionGlide';
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
  /* 한 번 굴리면 아래 칸까지 스르르 내려갑니다. 좁은 창에서는 켜지지 않습니다. */
  useSectionGlide();
  useEffect(() => {
    if (!showGuide) return;
    const timeout = window.setTimeout(() => setShowGuide(false), 3000);
    return () => window.clearTimeout(timeout);
  }, [showGuide]);
  /*
   * 어둠이 걷히는 정도를 스크롤에서 읽어 배경과 머리글에 넘깁니다.
   *
   * 스크롤 값을 그대로 쓰지 않고 한 박자 뒤따라가게 둡니다(followStep). 아래 칸으로 멎는
   * 스크롤은 한 번에 건너뛰어서, 그대로 넘기면 어둠이 순간에 걷힙니다. ParticleWave 가 별을
   * 흩는 속도와 같은 상수를 써야 배경과 별이 함께 밝아집니다.
   *
   * 따라갈 것이 남았을 때만 프레임을 돕니다. 멎어 있는 동안 도는 빈 루프를 두지 않습니다.
   */
  useEffect(() => {
    if (version !== '3') return;
    const layout = pageRef.current?.parentElement;
    let eased: number | null = null;
    let frame = 0;
    let lastTime = 0;

    const readTarget = () => {
      const hero = pageRef.current?.querySelector('.hero');
      if (!hero) return null;
      const rect = hero.getBoundingClientRect();
      return Math.min(1, Math.max(0, (-rect.top + 64) / rect.height));
    };

    const paint = (value: number) => {
      const page = pageRef.current;
      if (!page) return;
      const curve = value * value * (3 - 2 * value);
      page.style.setProperty('--scroll-light', `${curve * 100}%`);
      page.style.setProperty('--dark-opacity', `${1 - curve}`);
      layout?.style.setProperty('--home-header-light', `${curve * 100}%`);
      // The page's dark overlay also fades, so its visible white contribution is curve².
      layout?.style.setProperty('--home-header-background-light', `${curve * curve * 100}%`);
    };

    const follow = (time: number) => {
      frame = 0;
      const target = readTarget();
      if (target === null) return;
      const seconds = Math.min((time - (lastTime || time)) / 1000, .05);
      lastTime = time;
      /* 처음 한 번은 따라가지 않고 그 자리에서 시작합니다. 새로고침으로 중간에 들어왔을 때
         맨 위에서부터 밝아지는 장면이 다시 흐르면 안 됩니다. */
      eased = eased === null ? target : followStep(eased, target, seconds);
      if (Math.abs(target - eased) <= SCROLL_FOLLOW_EPSILON) eased = target;
      paint(eased);
      if (eased !== target) frame = requestAnimationFrame(follow);
    };

    const kick = () => {
      if (frame) return;
      lastTime = 0;
      frame = requestAnimationFrame(follow);
    };

    kick();
    window.addEventListener('scroll', kick, { passive: true });
    window.addEventListener('resize', kick);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener('scroll', kick);
      window.removeEventListener('resize', kick);
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

        {/*
          * 트렌드와 콘텐츠를 형제 칸으로 둡니다. 한 칸이 곧 한 화면이라, 콘텐츠를 트렌드 안에
          * 넣어 두면 트렌드 칸이 두 화면 높이가 되어 스크롤이 멎을 자리를 잡지 못합니다.
          */}
        <section className="trends-section" id="trends">
          <div className="trends-inner">
            <TodayTrends {...trendsDomain} />
          </div>
        </section>

        {version === '3' && <section className="featured-section" id="featured" aria-labelledby="featured-title">
          <div className="trends-inner">
            <div className="section-heading">
              <div><h2 id="featured-title">지금 주목할 만한 콘텐츠</h2><p>가을 패션에서 주목할 만한 콘텐츠를 모았습니다.</p></div>
            </div>
            <FeaturedContentsCarousel />
          </div>
        </section>}
      </main>
      <SiteFooter />
    </div>
  );
}
