import type { Metadata } from 'next';
import DraftFrame from '../../_components/draft-frame';
import EditorialDashboard from '../../_components/dashboard-v2';
export const metadata: Metadata = { title: 'ahead. — 초안.v2 · Editorial', description: '에디토리얼 스타일 비교 시안.' };
export default function Page() { return <DraftFrame version="v2"><EditorialDashboard/></DraftFrame>; }
