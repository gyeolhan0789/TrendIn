import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChevronIcon } from './myPageIcons';

/*
 * 시안의 마이페이지 무리는 회색 바탕 위에 흰 칸을 얹습니다. 바탕이 창 끝까지 닿아야 해서
 * 폭을 가둔 본문과 바탕 칠을 나눠 둡니다.
 */
export function MyPageScreen({ width, children }: { width: 'sm' | 'md' | 'lg' | 'wide'; children: ReactNode }) {
  return (
    <div className="mypage-canvas">
      <div className={`mypage-page mypage-page--${width}`}>{children}</div>
    </div>
  );
}

/** 마이페이지 아래 화면들이 머리에 세우는 길 표시. 되돌아갈 곳은 늘 마이페이지 하나입니다. */
export function MyPageCrumb({ current }: { current: string }) {
  return (
    <nav className="mypage-crumb" aria-label="현재 위치">
      <Link to="/mypage">마이페이지</Link>
      <ChevronIcon size={12} />
      <span aria-current="page">{current}</span>
    </nav>
  );
}

interface MyPageCardProps {
  title: string;
  /** 제목 왼쪽 네모 칸의 색결. 칸마다 다른 색을 써서 긴 화면에서 구역이 구분됩니다. */
  tone?: 'indigo' | 'amber' | 'blue' | 'emerald' | 'rose' | 'slate';
  icon?: ReactNode;
  action?: ReactNode;
  danger?: boolean;
  children: ReactNode;
}

/** 설정 화면들이 쓰는 흰 칸. 제목 줄 오른쪽에는 그 칸에서 할 일 하나가 설 수 있습니다. */
export function MyPageCard({ title, tone = 'indigo', icon, action, danger = false, children }: MyPageCardProps) {
  return (
    <section className={`mypage-card${danger ? ' is-danger' : ''}`}>
      <header className="mypage-card-head">
        <div className="mypage-card-title">
          {icon && <span className={`mypage-card-icon mypage-card-icon--${tone}`}>{icon}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

/**
 * 제목과 설명이 왼쪽, 스위치나 버튼이 오른쪽에 서는 한 줄입니다.
 * 설정 화면 대부분이 이 모양이라 따로 둡니다.
 */
export function MyPageRow({ title, description, children }: { title: string; description?: string; children?: ReactNode }) {
  return (
    <div className="mypage-row">
      <div className="mypage-row-text">
        <p className="mypage-row-title">{title}</p>
        {description && <p className="mypage-row-desc">{description}</p>}
      </div>
      {children}
    </div>
  );
}

/**
 * 아직 서버가 받아 주지 않는 자리에 답니다. 눌러도 되는 것처럼 보이게 두면 저장된 줄
 * 알고 지나가므로, 무엇이 없는지 글로 밝힙니다.
 */
export function MyPageNotice({ children }: { children: ReactNode }) {
  return <p className="mypage-notice">{children}</p>;
}
