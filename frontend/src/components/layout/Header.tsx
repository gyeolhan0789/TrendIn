import { NavLink, useLocation } from 'react-router-dom';
import { AccountMenu } from '../../features/auth/components/AccountMenu';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';

export function Header() {
  const location = useLocation();
  const isDashboard = location.pathname === '/dashboard';
  const session = useAuthSession();

  return (
    <header className={`app-header${isDashboard ? ' app-header--home' : ''}`}>
      <div className="header-inner">
        <NavLink className="brand" to="/" aria-label="TrendIn 홈">TrendIn<span className="brand-dot">.</span></NavLink>
        <nav className="main-nav" aria-label="주요 메뉴">
          <NavLink to="/dashboard">대시보드</NavLink>
          <NavLink to="/saved">저장한 트렌드</NavLink>
          <NavLink to="/mypage">마이페이지</NavLink>
        </nav>
        <div className="header-right">
          {isDashboard && <span className="header-collection">수집 1,291건 · 갱신 방금</span>}
          {/* 로그인 화면으로 보낼 때, 보고 있던 자리로 되돌아올 수 있게 경로를 함께 넘깁니다. */}
          {session
            ? <AccountMenu session={session} />
            : <NavLink className="header-login" to="/login" state={{ from: location.pathname }}>로그인</NavLink>}
        </div>
      </div>
    </header>
  );
}
