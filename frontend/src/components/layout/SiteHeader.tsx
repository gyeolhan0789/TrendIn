import { Link, NavLink, useLocation } from 'react-router-dom';
import { AccountMenu } from '../../features/auth/components/AccountMenu';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';

/*
 * 새 시안의 공용 헤더입니다. 메뉴 여섯 칸 가운데 아직 화면이 없는 곳이 있는데,
 * 칸을 빼면 가로 균형이 무너져서 자리는 그대로 두고 누를 수 없다는 것만 표시합니다.
 */
const navItems: { label: string; to?: string }[] = [
  { label: '홈', to: '/' },
  { label: '트렌드 탐색', to: '/dashboard' },
  { label: '관심 키워드', to: '/keywords' },
  { label: '국가별 트렌드', to: '/global' },
  { label: '저장된 트렌드', to: '/saved' },
  { label: '리포트' },
];

function BoltMark() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" fill="#4F46E5" stroke="#4F46E5" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function SiteHeader() {
  const location = useLocation();
  const session = useAuthSession();

  return (
    <header className="landing-header">
      <div className="landing-header-inner">
        <Link className="landing-brand" to="/" aria-label="TrendIn 홈">
          <BoltMark />
          <span>TrendIn</span>
        </Link>

        <nav className="landing-nav" aria-label="주요 메뉴">
          {navItems.map((item) => (item.to
            ? <NavLink key={item.label} to={item.to} end={item.to === '/'}>{item.label}</NavLink>
            : <span key={item.label} className="is-upcoming" aria-disabled="true" title="준비 중입니다">{item.label}</span>))}
        </nav>

        <div className="landing-header-right">
          <button type="button" className="landing-header-search" aria-label="검색">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          </button>
          {/* 로그인한 사람에게 다시 로그인·회원가입을 권할 이유가 없어, 그 자리를 계정 메뉴가 대신합니다. */}
          {session ? <AccountMenu session={session} /> : (
            <>
              <Link className="landing-btn landing-btn--ghost" to="/login" state={{ from: location.pathname }}>로그인</Link>
              <Link className="landing-btn landing-btn--dark" to="/signup">회원가입</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
