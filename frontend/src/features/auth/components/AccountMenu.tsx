import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLogout } from '../hooks/useLogout';
import type { AuthSession } from '../types/auth';

interface AccountMenuProps {
  session: AuthSession;
}

/** 이메일을 모르는 소셜 계정도 있어서, 머리글자를 못 뽑으면 기본 글자를 씁니다. */
function initialOf(email: string) {
  return (email.trim()[0] ?? 'T').toUpperCase();
}

export function AccountMenu({ session }: AccountMenuProps) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  // 바깥을 누르면 닫습니다. click은 메뉴 안의 버튼이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  const signOut = async () => {
    setOpen(false);
    await logoutMutation.mutateAsync();
    navigate('/', { replace: true });
  };

  return (
    <div className="header-account" ref={wrap}>
      <button
        type="button"
        className="avatar"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="내 계정"
        onClick={() => setOpen((current) => !current)}
      >
        {initialOf(session.email)}
      </button>
      {open && (
        <div className="header-account-menu" role="menu">
          <p className="header-account-email">{session.email || '연결된 소셜 계정'}</p>
          <Link role="menuitem" to="/mypage" onClick={() => setOpen(false)}>마이페이지</Link>
          <button role="menuitem" type="button" disabled={logoutMutation.isPending} onClick={signOut}>
            {logoutMutation.isPending ? '로그아웃 중…' : '로그아웃'}
          </button>
        </div>
      )}
    </div>
  );
}
