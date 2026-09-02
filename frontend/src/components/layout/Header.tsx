import { NavLink } from 'react-router-dom';

export function Header() {
  return (
    <header className="app-header">
      <div className="header-inner">
        <NavLink className="brand" to="/" aria-label="TrendIn 홈">TrendIn<span className="brand-dot">.</span></NavLink>
        <nav className="main-nav" aria-label="주요 메뉴">
          <NavLink to="/">대시보드</NavLink>
          <NavLink to="/saved-trends">저장한 트렌드</NavLink>
        </nav>
        <div className="header-right">
          <span className="avatar" aria-label="사용자 프로필">J</span>
        </div>
        </div>
    </header>
  );
}
