import type { Metadata } from 'next';
import DraftFrame from '../../_components/draft-frame';
import StageDashboard from '../../_components/dashboard-v3';

export const metadata: Metadata = {
  title: 'ahead. — 초안.v3 · Stage',
  description: '초안.v3: Top 5를 가로 순위 라인에서 보고 선택한 트렌드를 중앙에서 탐색하는 트렌드 무대.',
  openGraph: { title: 'ahead. — 초안.v3 · Stage', description: '다섯 가지 흐름, 하나씩 깊이 들여다보세요.' },
  twitter: { card: 'summary', title: 'ahead. — 초안.v3 · Stage', description: '시선이 머무는 흐름.' },
};

export default function Page() {
  return <DraftFrame version="v3"><StageDashboard/></DraftFrame>;
}
