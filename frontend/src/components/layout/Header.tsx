import { NavLink, useLocation } from 'react-router-dom';

export function Header() {
  const location = useLocation();
  const isHome = location.pathname === '/';

  return (
    <header className={`app-header${isHome ? ' app-header--home' : ''}`}>
      <div className="header-inner">
        <NavLink className="brand" to="/" aria-label="TrendIn 홈">TrendIn<span className="brand-dot">.</span></NavLink>
        <nav className="main-nav" aria-label="주요 메뉴">
          <NavLink to="/" end>대시보드</NavLink>
          <NavLink to="/saved">저장한 트렌드</NavLink>
        </nav>
        <div className="header-right">
          {isHome && <span className="header-collection">수집 1,291건 · 갱신 방금</span>}
          <span className="avatar" aria-label="사용자 프로필">J</span>
        </div>
      </div>
    </header>
  );
}
