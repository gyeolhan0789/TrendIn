import { apiClient } from '../../../api/client';
import type { ApiResponse, Page } from '../../../api/apiResponse';
import { unwrap } from '../../../api/apiResponse';
import { API_ENDPOINTS } from '../../../constants/apiEndpoints';
import type { Notification } from '../types/notification';

export async function getNotifications(page = 0, size = 10): Promise<Page<Notification>> {
  return unwrap(apiClient.get<ApiResponse<Page<Notification>>>(API_ENDPOINTS.members.notifications, {
    params: { page, size },
  }));
}

/** 뱃지에 쓰는 숫자입니다. 목록을 받지 않아도 알 수 있어 따로 둡니다. */
export async function getUnreadNotificationCount(): Promise<number> {
  const data = await unwrap(
    apiClient.get<ApiResponse<{ unreadCount: number }>>(API_ENDPOINTS.members.unreadNotificationCount),
  );
  return data.unreadCount;
}

export async function markNotificationAsRead(notificationId: number): Promise<void> {
  await apiClient.patch<ApiResponse<null>>(API_ENDPOINTS.members.notification(notificationId));
}

export async function markAllNotificationsAsRead(): Promise<void> {
  await apiClient.patch<ApiResponse<null>>(API_ENDPOINTS.members.readAllNotifications);
}
