export interface NotificationSettings {
  keywordSurgeEnabled: boolean;
  keywordDropEnabled: boolean;
  newTrendEnabled: boolean;
  trendTurningPointEnabled: boolean;
}

export type NotificationSettingKey = keyof NotificationSettings;

/** 설정 조회가 잠시 실패해도 화면과 네 가지 선택지를 유지하기 위한 서버 기본값입니다. */
export const defaultNotificationSettings: NotificationSettings = {
  keywordSurgeEnabled: true,
  keywordDropEnabled: true,
  newTrendEnabled: true,
  trendTurningPointEnabled: true,
};

/** 한 항목만 바꿀 때에도 서버가 요구하는 전체 설정 객체를 보존합니다. */
export function updateNotificationSetting(
  settings: NotificationSettings,
  key: NotificationSettingKey,
  enabled: boolean,
): NotificationSettings {
  return { ...settings, [key]: enabled };
}
