/** 지금 서버가 보내는 알림은 관심 키워드가 트렌드에 오를 때 한 가지뿐입니다. */
export type NotificationType = 'TREND_CHANGE';

export interface Notification {
  notificationId: number;
  trendId: number;
  notificationType: NotificationType;
  message: string;
  isRead: boolean;
  createdAt: string;
}
