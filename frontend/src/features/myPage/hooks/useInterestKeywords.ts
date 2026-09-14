import { useQuery } from '@tanstack/react-query';
import { getInterestKeywords } from '../api/myPageApi';
import { queryKeys } from '../../../utils/queryKeys';

/**
 * 등록한 관심 키워드 전부. 분야 거르기는 화면에서 하므로 여기서는 나누지 않습니다.
 * 등록 버튼도 이 목록을 보고 이미 담은 키워드인지 가립니다.
 */
export function useInterestKeywords() {
  return useQuery({ queryKey: queryKeys.myPage.interestKeywords, queryFn: () => getInterestKeywords() });
}
