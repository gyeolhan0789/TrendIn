import type { PropsWithChildren, ReactNode } from 'react';
import { Link } from 'react-router-dom';

interface AuthShellProps {
  /** 대문자 약물. 대시보드의 eyebrow와 같은 자리, 같은 서체입니다. */
  eyebrow: string;
  title: string;
  description: string;
  footer?: ReactNode;
}

/** 로그인·회원가입·OAuth 콜백이 함께 쓰는 한 칸짜리 틀입니다. */
export function AuthShell({ eyebrow, title, description, footer, children }: PropsWithChildren<AuthShellProps>) {
  return (
    <main className="auth-page">
      <div className="auth-card">
        <Link className="brand auth-brand" to="/" aria-label="TrendIn 홈">TrendIn<span className="brand-dot">.</span></Link>
        <p className="eyebrow auth-eyebrow">{eyebrow}</p>
        <h1 className="auth-title">{title}</h1>
        <p className="auth-description">{description}</p>
        {children}
      </div>
      {footer && <p className="auth-footer">{footer}</p>}
    </main>
  );
}
