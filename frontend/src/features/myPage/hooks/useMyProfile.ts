import { useQuery } from '@tanstack/react-query';
import { getMyProfile } from '../api/myPageApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useMyProfile() {
  return useQuery({ queryKey: queryKeys.myPage.profile, queryFn: getMyProfile });
}
