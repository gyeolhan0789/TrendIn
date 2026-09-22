import { useMemo } from 'react';
import { useInterestKeywords } from './useInterestKeywords';
import { useDeleteInterestKeyword, useRegisterInterestKeyword } from './useInterestKeywordMutations';

/**
 * 키워드 꼬리표를 눌러 담고 다시 눌러 빼는 데 필요한 것들.
 *
 * 홈의 추천 꼬리표와 트렌드 상세의 연관 키워드 칩이 같은 동작을 합니다. 두 곳이 각자
 * 표를 만들고 보내는 중을 가리다 보면 한쪽만 고쳐져 조용히 갈립니다 — 그 갈림이
 * "담았는데 안 담긴 것처럼 보인다" 로 나타나 알아채기 어렵습니다.
 *
 * 꼬리표의 모양은 부르는 쪽이 정합니다. 여기서 주는 것은 상태와 누를 때 할 일뿐입니다.
 */
export interface InterestKeywordToggle {
  /**
   * 담긴 목록을 받았는가. 받기 전에는 담긴 것을 가릴 수 없어, 누르면 이미 담은 것을
   * 또 보내게 됩니다. 부르는 쪽이 이때 단추를 잠급니다.
   */
  ready: boolean;
  registered: (keywordId: number) => boolean;
  /** 이 키워드에 대해 담기·빼기가 아직 오가는 중인가. */
  pending: (keywordId: number) => boolean;
  /** 담겼으면 빼고, 아니면 담습니다. */
  toggle: (keywordId: number, keyword: string) => void;
}

export function useInterestKeywordToggle(): InterestKeywordToggle {
  const interestKeywordsQuery = useInterestKeywords();
  const registerMutation = useRegisterInterestKeyword();
  const deleteMutation = useDeleteInterestKeyword();

  /*
   * 키워드 id → 등록 기록 id. 담겼는지만 보는 집합이 아니라 표인 이유는 빼는 길 때문입니다.
   * 뺄 때는 키워드가 아니라 등록 기록을 가리켜야 합니다 (`deleteInterestKeyword`).
   */
  const registeredBy = useMemo(
    () => new Map((interestKeywordsQuery.data ?? []).map((item) => [item.keywordId, item.interestKeywordId])),
    [interestKeywordsQuery.data],
  );

  return {
    ready: interestKeywordsQuery.isSuccess,
    registered: (keywordId) => registeredBy.has(keywordId),
    pending: (keywordId) => {
      if (registerMutation.isPending && registerMutation.variables?.keywordId === keywordId) return true;
      const interestKeywordId = registeredBy.get(keywordId);
      /* 등록 기록이 없으면 뺄 것도 없습니다. undefined 끼리 맞아떨어지는 것을 막습니다. */
      if (interestKeywordId === undefined) return false;
      return deleteMutation.isPending && deleteMutation.variables?.interestKeywordId === interestKeywordId;
    },
    toggle: (keywordId, keyword) => {
      const interestKeywordId = registeredBy.get(keywordId);
      /* undefined 로 갈라야 아래 분기에서 등록 기록 id 가 number 로 좁혀집니다. */
      if (interestKeywordId === undefined) registerMutation.mutate({ keywordId, keyword });
      else deleteMutation.mutate({ interestKeywordId, keyword });
    },
  };
}
