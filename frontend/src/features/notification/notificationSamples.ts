import type { Notification } from './types/notification';

/** 서버 알림이 없는 개발 환경에서 네 가지 유형의 표시를 확인하기 위한 샘플입니다. */
export const developmentNotificationSamples: Notification[] = [
  {
    notificationId: -1,
    trendId: -1,
    notificationType: 'KEYWORD_SURGE',
    message: "관심 키워드 '발레코어'가 급등했어요.",
    isRead: false,
    createdAt: '2026-09-20T14:25:00',
  },
  {
    notificationId: -2,
    trendId: -1,
    notificationType: 'NEW_TREND',
    message: "관심 키워드 '긱시크'가 신규 트렌드로 발견되었어요.",
    isRead: false,
    createdAt: '2026-09-20T12:10:00',
  },
  {
    notificationId: -3,
    trendId: -1,
    notificationType: 'TREND_TURNING_POINT',
    message: "관심 키워드 '레더 재킷'의 트렌드 유형이 신규에서 급상승으로 바뀌었어요.",
    isRead: true,
    createdAt: '2026-09-19T18:40:00',
  },
  {
    notificationId: -4,
    trendId: -1,
    notificationType: 'KEYWORD_DROP',
    message: "관심 키워드 '카고 팬츠'가 트렌드에서 급락했어요.",
    isRead: true,
    createdAt: '2026-09-19T09:30:00',
  },
  {
    notificationId: -5, trendId: -1, notificationType: 'KEYWORD_SURGE',
    message: "관심 키워드 '러닝코어'가 급등했어요.", isRead: true, createdAt: '2026-09-18T21:15:00',
  },
  {
    notificationId: -6, trendId: -1, notificationType: 'NEW_TREND',
    message: "관심 키워드 '모카 무스'가 신규 트렌드로 발견되었어요.", isRead: true, createdAt: '2026-09-18T15:20:00',
  },
  {
    notificationId: -7, trendId: -1, notificationType: 'KEYWORD_DROP',
    message: "관심 키워드 '고프코어'가 트렌드에서 급락했어요.", isRead: true, createdAt: '2026-09-18T10:05:00',
  },
  {
    notificationId: -8, trendId: -1, notificationType: 'TREND_TURNING_POINT',
    message: "관심 키워드 '스웨이드 재킷'의 트렌드 유형이 Top5에서 신규로 바뀌었어요.", isRead: true, createdAt: '2026-09-17T19:45:00',
  },
  {
    notificationId: -9, trendId: -1, notificationType: 'KEYWORD_SURGE',
    message: "관심 키워드 '드레이프 탑'이 급등했어요.", isRead: true, createdAt: '2026-09-17T11:30:00',
  },
  {
    notificationId: -10, trendId: -1, notificationType: 'NEW_TREND',
    message: "관심 키워드 '버터 옐로'가 신규 트렌드로 발견되었어요.", isRead: true, createdAt: '2026-09-16T16:40:00',
  },
  {
    notificationId: -11, trendId: -1, notificationType: 'KEYWORD_DROP',
    message: "관심 키워드 '테니스 스커트'가 트렌드에서 급락했어요.", isRead: true, createdAt: '2026-09-16T09:10:00',
  },
  {
    notificationId: -12, trendId: -1, notificationType: 'TREND_TURNING_POINT',
    message: "관심 키워드 '워크 재킷'의 트렌드 유형이 신규에서 급상승으로 바뀌었어요.", isRead: true, createdAt: '2026-09-15T20:25:00',
  },
  {
    notificationId: -13, trendId: -1, notificationType: 'KEYWORD_SURGE',
    message: "관심 키워드 '시어링 부츠'가 급등했어요.", isRead: true, createdAt: '2026-09-15T13:55:00',
  },
  {
    notificationId: -14, trendId: -1, notificationType: 'NEW_TREND',
    message: "관심 키워드 '브라운 데님'이 신규 트렌드로 발견되었어요.", isRead: true, createdAt: '2026-09-14T17:10:00',
  },
  {
    notificationId: -15, trendId: -1, notificationType: 'KEYWORD_DROP',
    message: "관심 키워드 '청키 스니커즈'가 트렌드에서 급락했어요.", isRead: true, createdAt: '2026-09-14T08:35:00',
  },
];
