import Link from './page-link';

export default function AppHeader({ active, savedCount, onSaved, onSettings }: {
  active: 'home' | 'world' | 'search'; savedCount: number; onSaved: () => void; onSettings: () => void;
}) {
  return <header className="site-header app-header"><div className="header-inner">
    <Link className="brand" href="/" aria-label="ahead 홈">ahead<span className="brand-dot">.</span></Link>
    <nav className="main-nav" aria-label="주 메뉴">
      {([['home', '/', '대시보드'], ['world', '/world', '세계 추이'], ['search', '/search', '트렌드 검색']] as const).map(([id, href, label]) =>
        <Link key={id} href={href} className={`nav-item ${active === id ? 'active' : ''}`} aria-current={active === id ? 'page' : undefined}>{label}</Link>)}
    </nav>
    <div className="header-right"><button className="header-saved" onClick={onSaved}>저장한 트렌드 <span>{savedCount}</span></button><button className="avatar" aria-label="내 관심 분야 설정" onClick={onSettings}>J</button></div>
  </div></header>;
}
