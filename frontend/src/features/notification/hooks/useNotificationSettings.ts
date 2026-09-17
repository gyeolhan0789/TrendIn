import { useSyncExternalStore } from 'react';
import {
  getNotificationSettings,
  setNotificationSettings,
  subscribeNotificationSettings,
} from '../api/notificationSettingsStorage';
import type { NotificationSettings } from '../types/notificationSettings';

/** 기기에 둔 알림 설정을 읽고 바꿉니다. 바꾸면 같은 값을 보던 다른 화면도 함께 따라옵니다. */
export function useNotificationSettings() {
  const settings = useSyncExternalStore(subscribeNotificationSettings, getNotificationSettings);
  const update = (next: (current: NotificationSettings) => NotificationSettings) => {
    setNotificationSettings(next(getNotificationSettings()));
  };
  return [settings, update] as const;
}
