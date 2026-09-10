import { showToast } from '../../../components/common/toast';
import { useInterestKeywords } from '../hooks/useInterestKeywords';

interface AddInterestKeywordButtonProps {
  keyword: string;
  /** 트렌드에서 온 키워드만 값이 있습니다. 없으면 이름으로만 등록합니다. */
  trendId?: string;
}

/**
 * 키워드 옆에 붙는 + 버튼. 어느 화면에 있든 그 키워드를 관심 키워드로 등록합니다.
 * 대개 상세로 가는 링크와 같은 칩 안에 놓이므로, 클릭이 링크까지 번지지 않게 막습니다.
 */
export function AddInterestKeywordButton({ keyword, trendId }: AddInterestKeywordButtonProps) {
  const { keywords, addKeyword } = useInterestKeywords();
  const registered = keywords.some((item) => (trendId ? item.trendId === trendId : item.keyword === keyword));

  return (
    <button
      type="button"
      className={`interest-add${registered ? ' is-registered' : ''}`}
      disabled={registered}
      aria-label={registered ? `${keyword} 관심 키워드에 등록됨` : `${keyword} 관심 키워드로 등록`}
      title={registered ? '이미 등록한 관심 키워드' : '관심 키워드로 등록'}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        const result = addKeyword({ keyword, trendId });
        if (result?.added) showToast({ message: `${keyword}을(를) 관심 키워드에 등록했습니다.`, type: 'success' });
      }}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {registered
          ? <polyline points="20 6 9 17 4 12" />
          : <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>}
      </svg>
    </button>
  );
}
