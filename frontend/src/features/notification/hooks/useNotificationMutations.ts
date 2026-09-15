import { useMutation, useQueryClient } from '@tanstack/react-query';
import { markAllNotificationsAsRead, markNotificationAsRead } from '../api/notificationApi';
import { getApiErrorMessage } from '../../../api/apiResponse';
import { showToast } from '../../../components/common/toast';
import { queryKeys } from '../../../utils/queryKeys';

/** 읽음 처리는 목록의 표시와 뱃지 숫자를 함께 바꾸므로 둘 다 다시 받습니다. */
function useInvalidateNotifications() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.list });
    void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.unreadCount });
  };
}

export function useMarkNotificationAsRead() {
  const invalidate = useInvalidateNotifications();

  return useMutation({
    mutationFn: (notificationId: number) => markNotificationAsRead(notificationId),
    onSuccess: invalidate,
    // 알림을 열어 보는 길은 막지 않습니다. 읽음 표시만 못 남긴 것이라 조용히 알립니다.
    onError: (error) => showToast({ message: getApiErrorMessage(error) ?? '알림을 읽음으로 바꾸지 못했습니다.', type: 'error' }),
  });
}

export function useMarkAllNotificationsAsRead() {
  const invalidate = useInvalidateNotifications();

  return useMutation({
    mutationFn: markAllNotificationsAsRead,
    onSuccess: () => {
      showToast({ message: '알림을 모두 읽음으로 바꿨습니다.', type: 'success' });
      invalidate();
    },
    onError: (error) => showToast({ message: getApiErrorMessage(error) ?? '알림을 읽음으로 바꾸지 못했습니다.', type: 'error' }),
  });
}
