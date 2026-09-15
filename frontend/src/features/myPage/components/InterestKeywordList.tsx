import { TagChip } from '../../trend/components/TagChip';
import { useDeleteInterestKeyword } from '../hooks/useInterestKeywordMutations';
import type { InterestKeyword } from '../types/myPage';

interface InterestKeywordListProps {
  keywords: InterestKeyword[];
  /** 분야 코드에 붙일 표시 이름. 서버가 관심 키워드에는 코드만 주므로 바깥에서 받아 씁니다. */
  domainNames: Map<string, string>;
}

export function InterestKeywordList({ keywords, domainNames }: InterestKeywordListProps) {
  const deleteMutation = useDeleteInterestKeyword();

  return (
    <div className="keywords-table">
      <div className="keywords-head">
        <span>키워드</span>
        <span>분야</span>
        <span />
      </div>

      <ul className="keywords-list">
        {keywords.map((item) => {
          const removing = deleteMutation.isPending
            && deleteMutation.variables?.interestKeywordId === item.interestKeywordId;
          const domain = domainNames.get(item.domain) ?? item.domain;

          return (
            <li className="keywords-row" key={item.interestKeywordId}>
              {/* 긴 키워드가 칸을 밀어내지 않도록, 말줄임 규칙이 걸린 칸 안에 둡니다. */}
              <span className="keywords-name">{item.keyword}</span>
              <div className="keywords-cat"><TagChip label={domain} /></div>
              <button
                type="button"
                className="keywords-remove"
                disabled={removing}
                aria-label={`${item.keyword} 관심 키워드에서 빼기`}
                title="관심 키워드에서 빼기"
                onClick={() => deleteMutation.mutate({ interestKeywordId: item.interestKeywordId, keyword: item.keyword })}
              >
                {removing
                  ? <span className="spinner spinner--small" aria-hidden="true" />
                  : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></svg>}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
