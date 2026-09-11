import { Link } from 'react-router-dom';
import type { RecommendedKeyword } from '../types/myPage';
import { AddInterestKeywordButton } from './AddInterestKeywordButton';

interface RecommendedKeywordsProps {
  recommendations: RecommendedKeyword[];
}

export function RecommendedKeywords({ recommendations }: RecommendedKeywordsProps) {
  if (recommendations.length === 0) return null;

  return (
    <section className="mypage-recommend" aria-label="추천 키워드">
      <header>
        <h2>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
          추천 키워드
        </h2>
        <span>내 관심사 기반 추천</span>
      </header>
      <div className="mypage-recommend-grid">
        {recommendations.map((recommendation) => (
          <div className="mypage-recommend-card" key={recommendation.trendId}>
            <Link to={`/trends/${recommendation.trendId}`}>
              <strong>{recommendation.keyword}</strong>
              <small>{recommendation.reason}</small>
            </Link>
            <AddInterestKeywordButton keyword={recommendation.keyword} trendId={recommendation.trendId} />
          </div>
        ))}
      </div>
    </section>
  );
}
