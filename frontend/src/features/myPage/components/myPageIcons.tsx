/*
 * 마이페이지 무리(마이페이지·프로필 편집·계정 설정·알림 설정·최근 활동)가 함께 쓰는 선
 * 아이콘입니다. 색은 감싼 칸에서 currentColor 로 내려 주고, 크기만 자리마다 정합니다.
 */

import type { ReactNode } from 'react';

interface IconProps { size?: number; }

function Icon({ size = 16, children }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  );
}

export function SurgeIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M23 6l-9.5 9.5-5-5L1 18" /><path d="M17 6h6v6" /></Icon>;
}

export function MailIcon({ size }: IconProps) {
  return <Icon size={size}><rect x="2" y="4" width="20" height="16" rx="2" /><path d="M22 6l-10 7L2 6" /></Icon>;
}

export function MoonIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" /></Icon>;
}

export function BellIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" /></Icon>;
}

export function UserIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></Icon>;
}

export function LockIcon({ size }: IconProps) {
  return <Icon size={size}><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" /></Icon>;
}

export function DownloadIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M7 10l5 5 5-5" /><path d="M12 15V3" /></Icon>;
}

export function WarnIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" /><path d="M12 9v4" /><path d="M12 17h.01" /></Icon>;
}

export function ClockIcon({ size }: IconProps) {
  return <Icon size={size}><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></Icon>;
}

export function BookmarkIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z" /></Icon>;
}

export function GridIcon({ size }: IconProps) {
  return <Icon size={size}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></Icon>;
}

export function GearIcon({ size }: IconProps) {
  return (
    <Icon size={size}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.6 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.6a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V10a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </Icon>
  );
}

export function ChevronIcon({ size = 14 }: IconProps) {
  return <Icon size={size}><path d="M9 18l6-6-6-6" /></Icon>;
}

export function PlusIcon({ size }: IconProps) {
  return <Icon size={size}><path d="M12 5v14M5 12h14" /></Icon>;
}
