export type NotificationType =
  | 'KEYWORD_SURGE'
  | 'KEYWORD_DROP'
  | 'NEW_TREND'
  | 'TREND_TURNING_POINT'
  | 'TREND_CHANGE';

export interface Notification {
  notificationId: number;
  trendId: number;
  notificationType: NotificationType;
  message: string;
  isRead: boolean;
  createdAt: string;
}
