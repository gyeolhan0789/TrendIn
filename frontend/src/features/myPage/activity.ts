import type { Notification } from '../notification/types/notification';
import type { SavedTrend } from '../savedTrend/types/savedTrend';

/**
 * 최근 활동 한 줄입니다.
 *
 * 서버에 활동 기록 API는 없습니다. 대신 시각이 남는 두 가지 — 받은 알림과 트렌드를 담은
 * 시각 — 을 모아 한 줄기로 세웁니다. 관심 키워드 등록은 등록 시각이 응답에 없어 넣지 못합니다.
 */
export interface Activity {
  id: string;
  kind: ActivityKind;
  text: string;
  /** YYYY-MM-DD. 날짜별로 묶을 때 씁니다. */
  date: string;
  /** HH:mm */
  time: string;
  trendId: number;
  /** 알림에서 온 줄만 갖습니다. 읽음으로 바꿀 때 이 값이 있어야 합니다. */
  notificationId?: number;
  /** 아직 읽지 않은 알림. 담은 트렌드는 읽고 말고가 없어 늘 false 입니다. */
  unread: boolean;
}

export type ActivityKind = 'surge' | 'saved';

export const activityLabels: Record<ActivityKind, string> = {
  surge: '급등',
  saved: '저장',
};

/*
 * 서버가 보내는 시각은 Asia/Seoul 기준입니다. 보는 사람의 시간대로 바꾸면 알림이 온 시각이
 * 달라 보이므로, 받은 문자열에서 필요한 자리만 잘라 씁니다. 알림함(NotificationBell)과 같은
 * 규칙입니다.
 */
const STAMP = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/;

function splitStamp(value: string) {
  const match = STAMP.exec(value);
  return match ? { date: match[1], time: match[2] } : undefined;
}

/** 오늘 날짜를 YYYY-MM-DD 로. 기기의 달력을 그대로 씁니다. */
function localDate(offsetDays = 0) {
  const day = new Date();
  day.setDate(day.getDate() + offsetDays);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
}

/** 날짜 머리글. 요 이틀만 말로 부르고, 그 앞은 날짜로 적습니다. */
export function formatActivityDate(date: string) {
  if (date === localDate()) return '오늘';
  if (date === localDate(-1)) return '어제';
  const match = /^\d{4}-(\d{2})-(\d{2})$/.exec(date);
  return match ? `${Number(match[1])}월 ${Number(match[2])}일` : date;
}

/**
 * 알림과 담은 트렌드를 한 줄기로 합쳐 최근 것부터 세웁니다.
 *
 * 시각 문자열이 같은 모양(YYYY-MM-DDTHH:mm…)이라 글자 그대로 견주어도 시간순이 됩니다.
 * 읽히지 않는 시각은 줄을 세울 수 없어 빼고 지나갑니다.
 */
export function buildActivities(notifications: Notification[], savedTrends: SavedTrend[]): Activity[] {
  const rows: (Activity & { stamp: string })[] = [];

  notifications.forEach((notification) => {
    const stamp = splitStamp(notification.createdAt);
    if (!stamp) return;
    rows.push({
      id: `noti-${notification.notificationId}`,
      kind: 'surge',
      text: notification.message,
      trendId: notification.trendId,
      notificationId: notification.notificationId,
      unread: !notification.isRead,
      stamp: notification.createdAt,
      ...stamp,
    });
  });

  savedTrends.forEach((trend) => {
    const stamp = splitStamp(trend.savedAt);
    if (!stamp) return;
    rows.push({
      id: `saved-${trend.savedTrendId}`,
      kind: 'saved',
      text: `"${trend.keyword}" 트렌드를 저장했습니다`,
      trendId: trend.trendId,
      unread: false,
      stamp: trend.savedAt,
      ...stamp,
    });
  });

  rows.sort((a, b) => b.stamp.localeCompare(a.stamp));
  return rows.map((row) => ({
    id: row.id,
    kind: row.kind,
    text: row.text,
    date: row.date,
    time: row.time,
    trendId: row.trendId,
    notificationId: row.notificationId,
    unread: row.unread,
  }));
}

/** 날짜가 같은 줄끼리 묶습니다. 이미 최근 것부터 서 있어서 순서는 그대로 둡니다. */
export function groupByDate(activities: Activity[]) {
  const groups: { date: string; items: Activity[] }[] = [];
  activities.forEach((activity) => {
    const last = groups[groups.length - 1];
    if (last && last.date === activity.date) last.items.push(activity);
    else groups.push({ date: activity.date, items: [activity] });
  });
  return groups;
}
