import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateMyProfile } from '../api/myPageApi';
import { queryKeys } from '../../../utils/queryKeys';

/** 닉네임을 고칩니다. 서버가 돌려준 프로필을 그대로 캐시에 얹어 헤더까지 곧바로 따라옵니다. */
export function useUpdateMyProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (nickname: string) => updateMyProfile(nickname),
    onSuccess: (profile) => queryClient.setQueryData(queryKeys.myPage.profile, profile),
  });
}
