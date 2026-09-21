import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import waveMark from '../../../assets/trendin-wave-mark.png';

/**
 * 로그인·회원가입 시안이 공유하는 바깥 틀입니다. 물결 배경, 머리줄, 왼쪽 소개 단을
 * 한 벌로 두고, 로그인에서만 홈과 같은 로고를 사용합니다. 오른쪽 카드 내용은 children 으로 받습니다.
 *
 * 높이는 .auth-scene 이 100dvh 안에 가두고, 창이 낮아지면 소개 쪽 여백부터 걷습니다.
 * 그래서 어느 화면을 붙이든 스크롤 없이 한 화면에 들어옵니다.
 *
 * className 은 그 여백을 화면마다 한 번 더 조일 자리입니다. 공통값으로 모자란 화면이
 * 자기 이름을 걸고 제 몫을 더 걷어 갈 수 있습니다.
 */
export function AuthScene({ children, className, useHomeLogo = false }: { children: ReactNode; className?: string; useHomeLogo?: boolean }) {
  return (
    <div className={`trendin-ui auth-scene${useHomeLogo ? ' auth-scene--login' : ''}${className ? ` ${className}` : ''}`}>

      {/* 시안의 물결 배경. 장식이라 읽히지 않게 두고 클릭도 통과시킵니다. */}
      <div className="auth-scene-wave" aria-hidden="true">
        <svg viewBox="0 0 800 320" preserveAspectRatio="none" fill="none">
          <defs>
            <linearGradient id="auth-scene-wave-a" x1="0" y1="0" x2="800" y2="320" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#c7d2fe" stopOpacity="0.5" />
              <stop offset="40%" stopColor="#a5b4fc" stopOpacity="0.3" />
              <stop offset="70%" stopColor="#e0e7ff" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#ddd6fe" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="auth-scene-wave-b" x1="0" y1="80" x2="800" y2="280" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.15" />
              <stop offset="50%" stopColor="#a78bfa" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#c4b5fd" stopOpacity="0.08" />
            </linearGradient>
            <linearGradient id="auth-scene-wave-light" x1="0" y1="0" x2="800" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#fffdf6" stopOpacity="0" />
              <stop offset="28%" stopColor="#fff5dc" stopOpacity="0.46" />
              <stop offset="55%" stopColor="#ffffff" stopOpacity="0.22" />
              <stop offset="82%" stopColor="#fff2d0" stopOpacity="0.38" />
              <stop offset="100%" stopColor="#fffdf6" stopOpacity="0" />
            </linearGradient>
            <radialGradient id="auth-scene-particle-halo">
              <stop offset="0%" stopColor="#ffffff" stopOpacity="0.88" />
              <stop offset="18%" stopColor="#fffdf7" stopOpacity="0.68" />
              <stop offset="48%" stopColor="#fff2cf" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#f1e8ff" stopOpacity="0" />
            </radialGradient>
            <filter id="auth-scene-wave-glow" x="-30%" y="-300%" width="160%" height="700%">
              <feGaussianBlur stdDeviation="3.2" />
            </filter>
          </defs>
          <path d="M0 200 Q100 140 200 180 T400 150 T600 190 T800 160 L800 320 L0 320Z" fill="url(#auth-scene-wave-a)" />
          <path d="M0 230 Q150 170 300 210 T500 180 T700 220 T800 190 L800 320 L0 320Z" fill="url(#auth-scene-wave-b)" />
          <path d="M0 260 Q120 220 250 250 T450 230 T650 260 T800 240 L800 320 L0 320Z" fill="#e0e7ff" fillOpacity="0.3" />
          {useHomeLogo && <g className="auth-scene-wave-glints">
            <g id="auth-scene-wave-glint-layer">
            <path className="auth-scene-wave-light auth-scene-wave-light--halo" d="M-40 239 Q115 177 276 211 T511 184 T724 218 T850 190" stroke="url(#auth-scene-wave-light)" />
            <path className="auth-scene-wave-light auth-scene-wave-light--back" d="M-40 239 Q115 177 276 211 T511 184 T724 218 T850 190" stroke="url(#auth-scene-wave-light)" />
            <path className="auth-scene-wave-light auth-scene-wave-light--front" d="M-30 199 Q101 143 211 178 T405 151 T603 189 T835 155" stroke="url(#auth-scene-wave-light)" />
            <path className="auth-scene-wave-light auth-scene-wave-light--middle" d="M-36 254 Q108 204 258 231 T487 205 T694 237 T842 211" stroke="url(#auth-scene-wave-light)" />
            <path className="auth-scene-wave-light auth-scene-wave-light--crest" d="M-28 184 Q96 128 232 166 T454 139 T676 178 T836 143" stroke="url(#auth-scene-wave-light)" />
            <path className="auth-scene-wave-gold-line" d="M42 246 Q158 201 286 219 T493 198 T688 225 T814 207" />
            <path className="auth-scene-wave-gold-line auth-scene-wave-gold-line--secondary" d="M-24 218 Q92 171 224 195 T448 169 T661 201 T838 174" />
            <path className="auth-scene-wave-gold-line auth-scene-wave-gold-line--tertiary" d="M-18 268 Q126 222 271 244 T506 220 T718 247 T842 226" />
            <path className="auth-scene-wave-gold-line auth-scene-wave-gold-line--quaternary" d="M12 204 Q139 157 274 184 T498 157 T710 191 T824 169" />
            <g className="auth-scene-wave-particle-halos" fill="url(#auth-scene-particle-halo)">
              <circle cx="58" cy="218" r="8" />
              <circle cx="112" cy="190" r="9" />
              <circle cx="168" cy="231" r="7" />
              <circle cx="247" cy="198" r="12" />
              <circle cx="318" cy="210" r="7" />
              <circle cx="366" cy="159" r="8" />
              <circle cx="411" cy="225" r="8" />
              <circle cx="470" cy="174" r="9" />
              <circle cx="515" cy="205" r="7" />
              <circle cx="548" cy="180" r="11" />
              <circle cx="603" cy="151" r="8" />
              <circle cx="654" cy="196" r="7" />
              <circle cx="706" cy="170" r="9" />
              <circle cx="748" cy="235" r="7" />
              <circle cx="774" cy="190" r="12" />
            </g>
            <g className="auth-scene-wave-shimmer">
              <circle cx="58" cy="218" r="2" />
              <circle cx="112" cy="190" r="2.4" />
              <circle cx="168" cy="231" r="1.8" />
              <circle cx="247" cy="198" r="3.1" />
              <circle cx="318" cy="210" r="1.8" />
              <circle cx="366" cy="159" r="2.2" />
              <circle cx="411" cy="225" r="2" />
              <circle cx="470" cy="174" r="2.2" />
              <circle cx="515" cy="205" r="1.8" />
              <circle cx="548" cy="180" r="3" />
              <circle cx="603" cy="151" r="2.1" />
              <circle cx="654" cy="196" r="1.8" />
              <circle cx="706" cy="170" r="2.3" />
              <circle cx="748" cy="235" r="1.8" />
              <circle cx="774" cy="190" r="3.2" />
            </g>
            <g className="auth-scene-wave-gold-spark">
              <circle cx="183" cy="207" r="1.8" />
              <circle cx="432" cy="200" r="2.2" />
              <circle cx="637" cy="216" r="1.7" />
              <circle cx="522" cy="158" r="1.5" />
              <circle cx="742" cy="207" r="1.6" />
            </g>
            </g>
            <use
              className="auth-scene-wave-glints-lower"
              href="#auth-scene-wave-glint-layer"
              transform="translate(0 450) scale(1 -1)"
            />
          </g>}
        </svg>
      </div>

      <header className="auth-scene-header">
        <Link className="auth-scene-brand" to="/" aria-label="TrendIn 홈">
          {useHomeLogo ? (
            <img className="landing-brand-mark" src={waveMark} width="40" height="26" alt="" aria-hidden="true" />
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#4F46E5" stroke="#4F46E5" strokeWidth="1.5" strokeLinejoin="round" />
            </svg>
          )}
          TrendIn
        </Link>
      </header>

      <div className="auth-scene-main">
        <section className="auth-scene-hero">
          {useHomeLogo
            ? <h1>세상을 움직이는<br /><span>트렌드를 담다</span></h1>
            : <h1>지금,<br />세상을 움직이는<br /><span>트렌드</span>를 담다</h1>}
          <p className="auth-scene-hero-lead">수많은 데이터 속에서 중요한 흐름을 찾아,<br />더 빠르고, 더 깊이 있게.</p>

          <div className="auth-scene-hero-stat">
            <div>
              <p className="auth-scene-hero-stat-value">+284%</p>
              <p className="auth-scene-hero-stat-label">언급량 증가</p>
            </div>
            <span className="auth-scene-hero-stat-mark" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2.5" strokeLinecap="round">
                <path d="M7 17l5-5 4 4 5-6" />
                <path d="M17 10h5v5" />
              </svg>
            </span>
          </div>

          {!useHomeLogo && <ul className="auth-scene-hero-features">
            <li>
              <span className="auth-scene-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <rect x="3" y="12" width="4" height="9" rx="1" />
                  <rect x="10" y="7" width="4" height="14" rx="1" />
                  <rect x="17" y="3" width="4" height="18" rx="1" />
                </svg>
              </span>
              <strong>실시간 트렌드 분석</strong>
              <span>지금 이 순간의 변화를 포착</span>
            </li>
            <li>
              <span className="auth-scene-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
                </svg>
              </span>
              <strong>AI 기반 인사이트</strong>
              <span>데이터가 만드는 새로운 시선</span>
            </li>
            <li>
              <span className="auth-scene-hero-feature-mark" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round">
                  <path d="M4 8h16M4 12h16M4 16h16" />
                </svg>
              </span>
              <strong>다양한 카테고리</strong>
              <span>관심 있는 모든 트렌드 한눈에</span>
            </li>
          </ul>}

          <div className="auth-scene-hero-foot">
            <p>지금도,<br />새로운 트렌드가 만들어지고 있어요.</p>
            <span className="auth-scene-hero-progress" aria-hidden="true"><i /></span>
          </div>
        </section>

        <section className="auth-scene-panel">{children}</section>
      </div>
    </div>
  );
}
