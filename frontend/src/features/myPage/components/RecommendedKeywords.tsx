import { useState } from 'react';
import { TagChip } from '../../trend/components/TagChip';
import { AddInterestKeywordButton } from './AddInterestKeywordButton';
import { pageList } from '../../../utils/pageList';
import type { RecommendedKeyword } from '../types/myPage';

/** 한 쪽에 여덟 개. 서버가 최대 40개를 주므로 다섯 쪽까지 나온다. */
const PAGE_SIZE = 8;

interface RecommendedKeywordsProps {
  recommendations: RecommendedKeyword[];
}

/**
 * 서버는 내 관심 키워드와 함께 언급된 정도만 알려 주고, 어느 키워드 때문에 권했는지는 주지 않습니다.
 * 그래서 추천 이유 대신 연관도를 그대로 보여 줍니다.
 *
 * 받은 목록을 화면에서 나눕니다. 추천은 관심 키워드가 바뀌어야 달라지므로, 쪽을 넘길 때마다
 * 서버를 다시 부를 이유가 없습니다.
 */
export function RecommendedKeywords({ recommendations }: RecommendedKeywordsProps) {
  const [page, setPage] = useState(1);

  if (recommendations.length === 0) return null;

  /*
   * 쪽 번호를 상태로 두지 않고 매번 조여 냅니다. 마지막 쪽의 키워드를 담으면 그 키워드가
   * 추천에서 빠져 쪽이 줄어드는데, 상태를 그대로 두면 빈 화면에 갇힙니다.
   */
  const totalPages = Math.max(1, Math.ceil(recommendations.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const shown = recommendations.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <section className="keywords-recommend" aria-label="추천 키워드">
      <header>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M13 3L4 14h7l-2 7 9-11h-7l2-7z" /></svg>
        <h2>추천 키워드</h2>
        <p>내 관심 키워드와 함께 언급되는 말입니다. 눌러서 바로 등록해 보세요.</p>
      </header>

      <div className="keywords-recommend-grid">
        {shown.map((recommendation) => (
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

      {totalPages > 1 && (
        <div className="keywords-recommend-pages">
          <div className="trendin-pages">
            {pageList(currentPage, totalPages).map((item, index) => (item === 'gap'
              ? <span className="trendin-page-gap" key={`gap-${index}`}>···</span>
              : (
                <button
                  key={item}
                  type="button"
                  className={item === currentPage ? 'is-current' : ''}
                  aria-current={item === currentPage ? 'page' : undefined}
                  onClick={() => setPage(item)}
                >
                  {item}
                </button>
              )))}
          </div>
        </div>
      )}
    </section>
  );
}
