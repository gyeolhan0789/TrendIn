import { Link } from 'react-router-dom';
import { ErrorState } from '../../components/common/ErrorState';
import { Skeleton } from '../../components/common/Skeleton';
import { PageContainer } from '../../components/layout/PageContainer';
import { SavedTrendList } from '../../features/savedTrend/components/SavedTrendList';
import { useDeleteSavedTrend } from '../../features/savedTrend/hooks/useDeleteSavedTrend';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';

export function SavedTrendPage() {
  const savedTrendsQuery = useSavedTrends();
  const deleteMutation = useDeleteSavedTrend();

  if (savedTrendsQuery.isLoading) return <PageContainer><SavedPageHeading /><Skeleton /></PageContainer>;
  if (savedTrendsQuery.isError) return <PageContainer><SavedPageHeading /><ErrorState onRetry={() => savedTrendsQuery.refetch()} /></PageContainer>;
  if (savedTrendsQuery.data?.length === 0) return <PageContainer><SavedPageHeading /><div className="empty-state"><OrbitMark /><h2>아직 비어 있는 컬렉션</h2><p>눈길이 가는 트렌드를 누르고 저장해보세요.<br />나만의 관심 흐름이 차곡차곡 쌓여요.</p><Link className="primary-button" to="/">오늘의 흐름 살펴보기</Link></div><SavedPageFooter /></PageContainer>;

  return (
    <PageContainer>
      <SavedPageHeading />
      <SavedTrendList trends={savedTrendsQuery.data ?? []} deletingTrendId={deleteMutation.isPending ? deleteMutation.variables : undefined} onDelete={(trendId) => deleteMutation.mutate(trendId)} />
      <SavedPageFooter />
    </PageContainer>
  );
}

function SavedPageHeading() {
  return <div className="saved-page-heading"><p className="eyebrow">TRENDIN / YOUR COLLECTION</p><h1>다시 만나고 싶은<br />흐름들<span className="accent">.</span></h1><p>발견한 순간을 저장해두세요.</p></div>;
}

function OrbitMark() {
  return <span className="orbit-mark" aria-hidden="true"><i /><i /><i /></span>;
}

function SavedPageFooter() {
  return <footer className="page-footer saved-page-footer"><span className="brand">TrendIn<span className="brand-dot">.</span></span><p>유행을 따라가기 전에, 흐름을 발견하세요.</p></footer>;
}
