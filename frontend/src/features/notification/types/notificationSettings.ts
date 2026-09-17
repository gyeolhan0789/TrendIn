/**
 * 알림을 어떤 항목까지 받을지 고른 값입니다.
 *
 * 백엔드에는 아직 이 설정을 받아 두는 API가 없습니다. 그래서 값은 기기에만 남고, 실제로
 * 나가는 알림(관심 키워드가 트렌드에 오를 때)은 이 값과 상관없이 옵니다. 화면이 그 점을
 * 함께 알립니다.
 */
export interface NotificationSettings {
  /** 끄면 아래 항목을 모두 잠급니다. 개별 값은 지우지 않고 그대로 둡니다. */
  master: boolean;
  trend: Record<TrendAlertKey, boolean>;
  report: Record<ReportAlertKey, boolean>;
  email: Record<EmailAlertKey, boolean>;
  quiet: QuietHours;
}

export type TrendAlertKey = 'surge' | 'plunge' | 'discovered' | 'turning';
export type ReportAlertKey = 'monthly' | 'custom';
export type EmailAlertKey = 'marketing' | 'system';

/** 이 시간 동안은 알림을 미룹니다. 시작이 종료보다 늦으면 자정을 넘긴 것으로 읽습니다. */
export interface QuietHours {
  enabled: boolean;
  start: string;
  end: string;
}
