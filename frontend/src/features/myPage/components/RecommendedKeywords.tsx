import { AddInterestKeywordButton } from './AddInterestKeywordButton';
import type { RecommendedKeyword } from '../types/myPage';

interface RecommendedKeywordsProps {
  recommendations: RecommendedKeyword[];
}

/**
 * 서버는 내 관심 키워드와 함께 언급된 정도만 알려 주고, 어느 키워드 때문에 권했는지는 주지 않습니다.
 * 그래서 추천 이유 대신 연관도를 그대로 보여 줍니다.
 */
export function RecommendedKeywords({ recommendations }: RecommendedKeywordsProps) {
  if (recommendations.length === 0) return null;

  return (
    <section className="mypage-recommend" aria-label="추천 키워드">
      <header>
        <h2>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
          추천 키워드
        </h2>
        <span>내 관심 키워드와 함께 언급되는 말</span>
      </header>
      <div className="mypage-recommend-grid">
        {recommendations.map((recommendation) => (
          <div className="mypage-recommend-card" key={recommendation.keywordId}>
            <span>
              <strong>{recommendation.keyword}</strong>
              <small>{recommendation.domain.name} · 연관도 {recommendation.relationScore}</small>
            </span>
            <AddInterestKeywordButton keywordId={recommendation.keywordId} keyword={recommendation.keyword} />
          </div>
        ))}
      </div>
    </section>
  );
}
