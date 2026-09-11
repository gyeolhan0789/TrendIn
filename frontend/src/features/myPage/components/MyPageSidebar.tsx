import type { MyProfile } from '../types/myPage';

interface MyPageSidebarProps {
  profile?: MyProfile;
  keywordCount: number;
  boardCount: number;
  alertCount: number;
}

/*
 * 사이드바 메뉴는 관심 키워드만 화면이 있습니다. 알림 설정과 계정 설정은 자리만 잡아두고
 * 링크로 만들지 않습니다. 갈 곳 없는 링크보다 준비 중이라고 밝히는 편이 덜 헷갈립니다.
 */
const pendingMenus = [
  { label: '알림 설정', icon: <><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" /></> },
  { label: '계정 설정', icon: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06A1.65 1.65 0 004.6 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.6a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></> },
];

export function MyPageSidebar({ profile, keywordCount, boardCount, alertCount }: MyPageSidebarProps) {
  return (
    <aside className="mypage-side">
      <div className="mypage-profile">
        <span className="mypage-profile-avatar" aria-hidden="true">{profile?.initial ?? ''}</span>
        <strong>{profile?.name ?? '\u00a0'}</strong>
        <span className="mypage-profile-email">{profile?.email ?? '\u00a0'}</span>
        <dl className="mypage-profile-stats">
          <div>
            <dt>관심 키워드</dt>
            <dd className="is-amber">{keywordCount}</dd>
          </div>
          <div>
            <dt>보드</dt>
            <dd className="is-accent">{boardCount}</dd>
          </div>
          <div>
            <dt>알림 설정</dt>
            <dd>{alertCount}</dd>
          </div>
        </dl>
      </div>

      <nav className="mypage-side-nav" aria-label="마이페이지 메뉴">
        <span className="mypage-side-link is-selected" aria-current="page">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" /></svg>
          관심 키워드
        </span>
        {pendingMenus.map((menu) => (
          <span className="mypage-side-link" key={menu.label} aria-disabled="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">{menu.icon}</svg>
            {menu.label}
            <small>준비 중</small>
          </span>
        ))}
      </nav>
    </aside>
  );
}
