import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../hooks/useNotifications';
import { MAX_NOTIFICATION_COUNT, NOTIFICATION_PAGE_SIZE } from '../notificationPagination';
import { useUnreadNotificationCount } from '../hooks/useUnreadNotificationCount';
import { useMarkAllNotificationsAsRead, useMarkNotificationAsRead } from '../hooks/useNotificationMutations';
import { useTrendDetailLink } from '../../trend/trendDetailLink';
import type { Notification } from '../types/notification';
import { formatNotificationMessage, notificationTypeClass, notificationTypeLabels } from '../notificationPresentation';
import { developmentNotificationSamples } from '../notificationSamples';

const MAX_BADGE_COUNT = 99;
const SAMPLE_READ_STORAGE_KEY = 'trendin-notification-sample-read-v1';

function readStoredSampleIds() {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(SAMPLE_READ_STORAGE_KEY) ?? '[]');
    return new Set(Array.isArray(value) ? value.filter((id): id is number => typeof id === 'number') : []);
  } catch {
    return new Set<number>();
  }
}

/*
 * 서버가 보내는 시각은 Asia/Seoul 기준입니다. 보는 사람의 시간대로 바꾸면 알림이 온 시각이
 * 달라 보이므로, 받은 문자열에서 필요한 자리만 잘라 씁니다.
 */
function formatSentAt(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  return match ? `${match[2]}.${match[3]} ${match[4]}:${match[5]}` : value;
}

export function NotificationBell() {
  const openDetail = useTrendDetailLink();
  const [open, setOpen] = useState(false);
  const [readSampleIds, setReadSampleIds] = useState<Set<number>>(readStoredSampleIds);
  const [sampleVisibleCount, setSampleVisibleCount] = useState(NOTIFICATION_PAGE_SIZE);
  const wrap = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const unreadCountQuery = useUnreadNotificationCount();
  const notificationsQuery = useNotifications(open);
  const markAsRead = useMarkNotificationAsRead();
  const markAllAsRead = useMarkAllNotificationsAsRead();

  // 바깥을 누르면 닫습니다. click은 목록 안의 버튼이 사라진 뒤에 와서 pointerdown을 씁니다.
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!wrap.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SAMPLE_READ_STORAGE_KEY, JSON.stringify([...readSampleIds]));
    } catch {
      // 개발용 샘플 상태이므로 저장소를 쓸 수 없으면 현재 화면에서만 유지합니다.
    }
  }, [readSampleIds]);

  const notifications = notificationsQuery.data?.pages.flatMap((page) => page.content) ?? [];
  const usingSamples = import.meta.env.DEV && notificationsQuery.isSuccess && notifications.length === 0;
  const availableNotifications = usingSamples
    ? developmentNotificationSamples.map((notification) => ({
      ...notification,
      isRead: notification.isRead || readSampleIds.has(notification.notificationId),
    }))
    : notifications;
  const displayedNotifications = usingSamples
    ? availableNotifications.slice(0, sampleVisibleCount)
    : availableNotifications.slice(0, MAX_NOTIFICATION_COUNT);
  const unreadCount = usingSamples
    ? availableNotifications.filter((notification) => !notification.isRead).length
    : (unreadCountQuery.data ?? 0);
  const canLoadMore = usingSamples
    ? sampleVisibleCount < Math.min(availableNotifications.length, MAX_NOTIFICATION_COUNT)
    : notificationsQuery.hasNextPage;

  /** 알림을 열면 읽음으로 바꾸고 그 트렌드로 갑니다. 읽음 처리가 실패해도 이동은 막지 않습니다. */
  const openNotification = (notification: Notification) => {
    if (notification.notificationId < 0) {
      setReadSampleIds((current) => new Set(current).add(notification.notificationId));
      return;
    }
    if (!notification.isRead) markAsRead.mutate(notification.notificationId);
    setOpen(false);
    const { to, state, replace } = openDetail(notification.trendId);
    navigate(to, { state, replace });
  };

  return (
    <div className="header-notification" ref={wrap}>
      <button
        type="button"
        className="header-notification-button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={unreadCount > 0 ? `알림 ${unreadCount}건 안 읽음` : '알림'}
        onClick={() => setOpen((current) => !current)}
      >
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="header-notification-badge">{unreadCount > MAX_BADGE_COUNT ? `${MAX_BADGE_COUNT}+` : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="header-notification-menu" role="menu">
          <div className="header-notification-head">
            <strong>알림</strong>
            <button
              type="button"
              disabled={unreadCount === 0 || markAllAsRead.isPending}
              onClick={() => {
                if (usingSamples) {
                  setReadSampleIds(new Set(developmentNotificationSamples.map(({ notificationId }) => notificationId)));
                } else {
                  markAllAsRead.mutate();
                }
              }}
            >
              모두 읽음
            </button>
          </div>

          {notificationsQuery.isLoading && <p className="header-notification-empty">불러오는 중…</p>}
          {notificationsQuery.isError && <p className="header-notification-empty">알림을 불러오지 못했습니다.</p>}
          {notificationsQuery.isSuccess && notifications.length === 0 && !usingSamples && (
            <p className="header-notification-empty">
              아직 새로운 알림이 없어요.<br />관심 키워드에 변화가 생기면 알려드릴게요.
            </p>
          )}

          {displayedNotifications.length > 0 && (
            <ul className="header-notification-list">
              {displayedNotifications.map((notification) => (
                <li key={notification.notificationId} className={notification.isRead ? '' : 'is-unread'}>
                  <button type="button" onClick={() => openNotification(notification)}>
                    <span className="header-notification-copy">
                      <span className={`header-notification-type ${notificationTypeClass(notification.notificationType)}`}>
                        {notificationTypeLabels[notification.notificationType]}
                      </span>
                      <span>{formatNotificationMessage(notification)}</span>
                    </span>
                    <time dateTime={notification.createdAt}>{formatSentAt(notification.createdAt)}</time>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {canLoadMore && (
            <button
              type="button"
              className="header-notification-more"
              disabled={notificationsQuery.isFetchingNextPage}
              onClick={() => {
                if (usingSamples) {
                  setSampleVisibleCount((current) => Math.min(current + NOTIFICATION_PAGE_SIZE, MAX_NOTIFICATION_COUNT));
                } else {
                  void notificationsQuery.fetchNextPage();
                }
              }}
            >
              {notificationsQuery.isFetchingNextPage ? '불러오는 중…' : '이전 알림 더 보기'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
