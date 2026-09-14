import type { MouseEvent } from 'react';
import { useToggleSavedTrend } from '../hooks/useToggleSavedTrend';

interface BookmarkButtonProps {
  trendId: number;
  keyword: string;
  /** 놓이는 자리마다 크기와 색이 달라 바깥에서 정합니다. 담긴 상태는 is-saved 로 표시합니다. */
  className?: string;
}

/**
 * 트렌드를 담고 빼는 버튼입니다. 담긴 키워드는 북마크가 채워집니다.
 *
 * 링크 안에 놓이는 자리가 있어 눌렀을 때 이동이 함께 일어나지 않도록 기본 동작을 막습니다.
 */
export function BookmarkButton({ trendId, keyword, className = 'home-bookmark' }: BookmarkButtonProps) {
  const { isSaved, isReady, pendingTrendId, toggle } = useToggleSavedTrend();
  const saved = isSaved(trendId);
  const pending = pendingTrendId === trendId;

  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    toggle({ trendId, keyword });
  };

  return (
    <button
      className={`${className}${saved ? ' is-saved' : ''}`}
      type="button"
      title={saved ? '담기 취소' : '담기'}
      aria-label={`${keyword} ${saved ? '담기 취소' : '담기'}`}
      aria-pressed={saved}
      // 담긴 상태를 아직 모르는 동안 누르면 담기와 취소가 뒤바뀔 수 있어 기다립니다.
      disabled={!isReady || pending}
      onClick={handleClick}
    >
      {pending
        ? <span className="spinner spinner--small" aria-hidden="true" />
        : (
          <svg viewBox="0 0 13 16" width="13" height="16" fill={saved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.3" aria-hidden="true">
            <path d="M1.5 1.5h10v13l-5-3.6-5 3.6z" />
          </svg>
        )}
    </button>
  );
}
