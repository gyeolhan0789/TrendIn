import type { Notification, NotificationType } from './types/notification';

export const notificationTypeLabels: Record<NotificationType, string> = {
  KEYWORD_SURGE: '상승',
  KEYWORD_DROP: '하락',
  NEW_TREND: '신규',
  TREND_TURNING_POINT: '주목',
  TREND_CHANGE: '트렌드',
};

export function notificationTypeClass(type: NotificationType) {
  return `is-${type.toLowerCase().replaceAll('_', '-')}`;
}

const KEYWORD_IN_QUOTES = /['“"]([^'”"]+)['”"]/;
const TURNING_DESTINATION = /에서\s+(.+?)(?=으로\s+바뀌었어요|로\s+바뀌었어요)/;

function subjectParticle(keyword: string) {
  const last = keyword.codePointAt(keyword.length - 1);
  if (last === undefined || last < 0xac00 || last > 0xd7a3) return '가';
  return (last - 0xac00) % 28 === 0 ? '가' : '이';
}

/** API 메시지에서 실제 키워드와 전환 유형을 살려 알림 문구를 한 가지 말투로 맞춥니다. */
export function formatNotificationMessage(notification: Pick<Notification, 'notificationType' | 'message'>) {
  const keyword = KEYWORD_IN_QUOTES.exec(notification.message)?.[1];
  if (!keyword) return notification.message;

  const subject = `“${keyword}”${subjectParticle(keyword)}`;
  switch (notification.notificationType) {
    case 'KEYWORD_SURGE': return `${subject} 빠르게 상승하고 있어요.`;
    case 'KEYWORD_DROP': return `${subject} 트렌드에서 벗어났어요.`;
    case 'NEW_TREND': return `${subject} 새로운 트렌드로 떠올랐어요.`;
    case 'TREND_TURNING_POINT': {
      const destination = TURNING_DESTINATION.exec(notification.message)?.[1];
      return destination
        ? `${subject} ${destination} 트렌드로 전환됐어요.`
        : `${subject} 새로운 흐름으로 전환됐어요.`;
    }
    default: return notification.message;
  }
}
