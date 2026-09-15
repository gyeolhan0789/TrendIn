import { TagChip } from '../../trend/components/TagChip';
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
    <section className="keywords-recommend" aria-label="추천 키워드">
      <header>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" /></svg>
        <h2>추천 키워드</h2>
        <p>내 관심 키워드와 함께 언급되는 말입니다. 눌러서 바로 등록해 보세요.</p>
      </header>

      <div className="keywords-recommend-grid">
        {recommendations.map((recommendation) => (
          <div className="keywords-recommend-card" key={recommendation.keywordId}>
            <span>
              <strong>{recommendation.keyword}</strong>
              <small>
                <TagChip label={recommendation.domain.name} />
                연관도 {recommendation.relationScore}
              </small>
            </span>
            <AddInterestKeywordButton keywordId={recommendation.keywordId} keyword={recommendation.keyword} />
          </div>
        ))}
      </div>
    </section>
  );
}
