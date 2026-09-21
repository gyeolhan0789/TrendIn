import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getNotificationSettings, updateNotificationSettings } from '../api/notificationApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useNotificationSettings() {
  return useQuery({
    queryKey: queryKeys.notifications.settings,
    queryFn: getNotificationSettings,
  });
}

export function useUpdateNotificationSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateNotificationSettings,
    onSuccess: (settings) => {
      queryClient.setQueryData(queryKeys.notifications.settings, settings);
    },
  });
}
