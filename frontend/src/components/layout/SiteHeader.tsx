import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { AccountMenu } from '../../features/auth/components/AccountMenu';
import { NotificationBell } from '../../features/notification/components/NotificationBell';
import { useAuthSession } from '../../features/auth/hooks/useAuthSession';
import waveMark from '../../assets/trendin-wave-mark.png';

/*
 * 새 시안의 공용 헤더입니다. 지금 선 다섯 칸은 모두 갈 곳이 있습니다.
 *
 * 갈 곳(to)이 없는 칸은 흐리게 세웁니다. 시안이 먼저 나오고 화면이 뒤따라오는 일이
 * 되풀이되는데, 칸을 아예 빼면 그동안 가로 균형이 무너지기 때문입니다.
 */
const navItems: { label: string; to?: string }[] = [
  { label: '홈', to: '/' },
  { label: '트렌드 탐색', to: '/dashboard' },
  { label: '관심 키워드', to: '/interest-keywords' },
  { label: '국가별 트렌드', to: '/global' },
  { label: '저장된 트렌드', to: '/saved' },
];

/** 여는 단추가 aria-controls 로 가리킬 이름입니다. 한 쪽에 헤더가 하나라 고정 값으로 둡니다. */
const MENU_ID = 'site-header-menu';

export function SiteHeader() {
  const location = useLocation();
  const session = useAuthSession();
  const [menuOpen, setMenuOpen] = useState(false);
  const header = useRef<HTMLElement>(null);

  /* 메뉴로 다른 화면에 간 뒤에도 열려 있으면 그 화면을 덮습니다. */
  useEffect(() => setMenuOpen(false), [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    // 바깥을 누르면 닫습니다. click 은 메뉴 안의 링크가 사라진 뒤에 와서 pointerdown 을 씁니다.
    const closeOnAway = (event: PointerEvent) => {
      if (!header.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('pointerdown', closeOnAway);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnAway);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [menuOpen]);

  /*
   * 가로줄과 펼침 카드가 같은 칸을 보여 줍니다. 한 벌만 두면 둘이 어긋날 일이 없습니다.
   * 보이는 것은 늘 하나뿐이라(좁으면 가로줄이, 넓으면 카드가 CSS 로 접힙니다) 읽어 주는 쪽에도
   * 같은 메뉴가 두 번 들리지 않습니다.
   */
  const navLinks = navItems.map((item) => (item.to
    ? <NavLink key={item.label} to={item.to} end={item.to === '/'}>{item.label}</NavLink>
    : <span key={item.label} className="is-upcoming" aria-disabled="true" title="준비 중입니다">{item.label}</span>));

  return (
    <header className="landing-header" ref={header}>
      <div className="landing-header-inner">
        <Link className="landing-brand" to="/" aria-label="TrendIn 홈">
          <img className="landing-brand-mark" src={waveMark} width="40" height="26" alt="" aria-hidden="true" />
          <span>TrendIn</span>
        </Link>

        <nav className="landing-nav" aria-label="주요 메뉴">{navLinks}</nav>

        <div className="landing-header-right">
          {/* 로그인한 사람에게 다시 로그인·회원가입을 권할 이유가 없어, 그 자리를 계정 메뉴가 대신합니다. */}
          {session ? (
            <>
              <NotificationBell />
              <AccountMenu session={session} />
            </>
          ) : (
            <>
              <Link className="landing-btn landing-btn--ghost" to="/login" state={{ from: location.pathname }}>로그인</Link>
              <Link className="landing-btn landing-btn--dark" to="/signup">회원가입</Link>
            </>
          )}
        </div>

        {/* 가로줄이 접히는 폭에서만 섭니다. 넓은 화면에서는 CSS 가 이 단추를 감춥니다. */}
        <button
          type="button"
          className="landing-menu-toggle"
          aria-label="주요 메뉴"
          aria-expanded={menuOpen}
          aria-controls={MENU_ID}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            {menuOpen
              ? <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>
              : <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></>}
          </svg>
        </button>
      </div>

      {/*
        * 가로줄의 landing-nav 를 같이 달지 않습니다. 랜딩 헤더는 배경이 어두워 글자를 밝게
        * 칠하는데, 이 카드는 흰 바탕이라 그 색을 물려받으면 글자가 배경에 묻힙니다.
        */}
      {menuOpen && (
        <nav className="landing-menu" id={MENU_ID} aria-label="주요 메뉴">{navLinks}</nav>
      )}
    </header>
  );
}
