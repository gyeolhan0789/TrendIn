import type { Metadata } from 'next';
import DashboardV1 from './_components/dashboard-v1';

export const metadata: Metadata = {
  title: 'ahead. — 나의 트렌드',
  description: '내 관심 분야의 현재 Top 5와 새롭게 떠오르는 트렌드를 한눈에.',
  openGraph: { title: 'ahead. — 나의 트렌드', description: '당신의 취향, 그다음의 발견.' },
  twitter: { card: 'summary', title: 'ahead. — 나의 트렌드', description: '내 관심 분야의 다음 흐름을 발견하세요.' },
};
export default function Page() { return <DashboardV1/>; }
