import { useInfiniteQuery } from '@tanstack/react-query';
import { getNotifications } from '../api/notificationApi';
import { queryKeys } from '../../../utils/queryKeys';
import { getNextNotificationPage, NOTIFICATION_PAGE_SIZE } from '../notificationPagination';

/** 최근 것부터 받고, 더 있으면 눌러서 이어 받습니다. */
export function useNotifications(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: queryKeys.notifications.list,
    queryFn: ({ pageParam }) => getNotifications(pageParam, NOTIFICATION_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: getNextNotificationPage,
    // 알림함을 열기 전에는 받아 둘 필요가 없습니다. 뱃지 숫자는 따로 조회합니다.
    enabled,
  });
}
