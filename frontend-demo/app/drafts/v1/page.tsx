import type { Metadata } from 'next';
import DraftFrame from '../../_components/draft-frame';
import DashboardV1 from '../../_components/dashboard-v1';

export const metadata: Metadata = {
  title: 'ahead. — 초안.v1 · Grid',
  description: '초안.v1: 사용자가 보존한 흰 배경의 Top 5 카드 그리드 대시보드.',
  openGraph: { title: 'ahead. — 초안.v1 · Grid', description: '보존한 화이트 카드 그리드 시안.' },
  twitter: { card: 'summary', title: 'ahead. — 초안.v1 · Grid', description: '관심 분야 하나에 집중하는 트렌드 대시보드.' },
};

export default function Page() {
  return <DraftFrame version="v1"><DashboardV1/></DraftFrame>;
}
