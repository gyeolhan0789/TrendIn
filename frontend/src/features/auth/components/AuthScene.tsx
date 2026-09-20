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
    <div className={`trendin-ui auth-scene${className ? ` ${className}` : ''}`}>

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
          </defs>
          <path d="M0 200 Q100 140 200 180 T400 150 T600 190 T800 160 L800 320 L0 320Z" fill="url(#auth-scene-wave-a)" />
          <path d="M0 230 Q150 170 300 210 T500 180 T700 220 T800 190 L800 320 L0 320Z" fill="url(#auth-scene-wave-b)" />
          <path d="M0 260 Q120 220 250 250 T450 230 T650 260 T800 240 L800 320 L0 320Z" fill="#e0e7ff" fillOpacity="0.3" />
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
          <h1>지금,<br />세상을 움직이는<br /><span>트렌드</span>를 담다</h1>
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

          <ul className="auth-scene-hero-features">
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
          </ul>

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
