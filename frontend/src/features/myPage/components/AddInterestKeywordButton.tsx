import type { MouseEvent } from 'react';
import { useInterestKeywords } from '../hooks/useInterestKeywords';
import { useRegisterInterestKeyword } from '../hooks/useInterestKeywordMutations';

interface AddInterestKeywordButtonProps {
  keywordId: number;
  keyword: string;
}

/**
 * 키워드 옆에 붙는 + 버튼. 어느 화면에 있든 그 키워드를 관심 키워드로 등록합니다.
 *
 * 등록은 이름이 아니라 키워드 식별자로 하므로, 서버가 아는 키워드에만 붙일 수 있습니다.
 * 대개 다른 곳으로 가는 링크와 같은 칩 안에 놓여 클릭이 번지지 않게 막습니다.
 */
export function AddInterestKeywordButton({ keywordId, keyword }: AddInterestKeywordButtonProps) {
  const interestKeywordsQuery = useInterestKeywords();
  const registerMutation = useRegisterInterestKeyword();

  const registered = interestKeywordsQuery.data?.some((item) => item.keywordId === keywordId) ?? false;
  const pending = registerMutation.isPending && registerMutation.variables?.keywordId === keywordId;

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    registerMutation.mutate({ keywordId, keyword });
  };

  return (
    <button
      type="button"
      className={`interest-add${registered ? ' is-registered' : ''}`}
      // 등록 여부를 아직 모르는 동안 누르면 이미 등록한 키워드를 또 보내게 됩니다.
      disabled={registered || pending || !interestKeywordsQuery.isSuccess}
      aria-label={registered ? `${keyword} 관심 키워드에 등록됨` : `${keyword} 관심 키워드로 등록`}
      title={registered ? '이미 등록한 관심 키워드' : '관심 키워드로 등록'}
      onClick={handleClick}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {registered
          ? <polyline points="20 6 9 17 4 12" />
          : <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>}
      </svg>
    </button>
  );
}
