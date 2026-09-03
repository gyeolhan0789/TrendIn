import { Link } from 'react-router-dom';
import { PageContainer } from '../../components/layout/PageContainer';

export function SavedTrendPage() {
  return (
    <PageContainer>
      <section className="saved-page-heading">
        <p className="eyebrow">TRENDIN / YOUR COLLECTION</p>
        <h1>저장한 트렌드<span className="accent">.</span></h1>
        <p>발견한 흐름을 다시 만나보세요.</p>
        <Link className="primary-button" to="/">메인으로 돌아가기</Link>
      </section>
    </PageContainer>
  );
}
