import { useQuery } from '@tanstack/react-query';
import { getUnreadNotificationCount } from '../api/notificationApi';
import { queryKeys } from '../../../utils/queryKeys';

export function useUnreadNotificationCount() {
  return useQuery({ queryKey: queryKeys.notifications.unreadCount, queryFn: getUnreadNotificationCount });
}
