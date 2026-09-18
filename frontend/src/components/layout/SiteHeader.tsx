import { Link, NavLink, useLocation } from 'react-router-dom';
import { AccountMenu } from '../../features/auth/components/AccountMenu';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';

/*
 * 새 시안의 공용 헤더입니다. 이제 여섯 칸 모두 갈 곳이 있습니다.
 *
 * 갈 곳(to)이 없는 칸은 여전히 흐리게 세웁니다. 시안이 먼저 나오고 화면이 뒤따라오는 일이
 * 되풀이되는데, 칸을 아예 빼면 그동안 가로 균형이 무너지기 때문입니다.
 */
const navItems: { label: string; to?: string }[] = [
  { label: '홈', to: '/' },
  { label: '트렌드 탐색', to: '/dashboard' },
  { label: '관심 키워드', to: '/keywords' },
  { label: '국가별 트렌드', to: '/global' },
  { label: '저장된 트렌드', to: '/saved' },
  { label: '리포트', to: '/report' },
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
