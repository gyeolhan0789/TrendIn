import type { Metadata } from 'next';
import './globals.css';
import './panels.css';
import './drafts.css';
import './editorial.css';
import './stage.css';
import './explore.css';
import './spread.css';

export const metadata: Metadata = {
  title: 'ahead. — 오늘의 흐름, 한발 먼저',
  description: '내 관심 분야에서 새롭게 떠오르는 흐름을 발견하는 개인화 트렌드 대시보드. 현재 트렌드 Top 5부터 신규·급상승 키워드까지.',
  openGraph: { title: 'ahead. — 오늘의 흐름, 한발 먼저', description: '수많은 이야기 속, 당신에게 필요한 다음 트렌드.', locale: 'ko_KR', type: 'website' },
  twitter: { card: 'summary', title: 'ahead. — 오늘의 흐름, 한발 먼저', description: '내 관심 분야의 다음 트렌드를 발견하세요.' },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
