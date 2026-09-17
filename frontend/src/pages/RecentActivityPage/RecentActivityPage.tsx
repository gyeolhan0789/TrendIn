import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MyPageCrumb, MyPageNotice, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import { BookmarkIcon, ChevronIcon, SurgeIcon } from '../../features/myPage/components/myPageIcons';
import { activityLabels, buildActivities, formatActivityDate, groupByDate } from '../../features/myPage/activity';
import { useNotifications } from '../../features/notification/hooks/useNotifications';
import { useMarkAllNotificationsAsRead, useMarkNotificationAsRead } from '../../features/notification/hooks/useNotificationMutations';
import { useUnreadNotificationCount } from '../../features/notification/hooks/useUnreadNotificationCount';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import { useTrendDetailLink } from '../../features/trend/trendDetailLink';
import type { ActivityKind } from '../../features/myPage/activity';

const ALL = 'all';

const filters: { value: string; label: string }[] = [
  { value: ALL, label: '전체' },
  { value: 'surge', label: activityLabels.surge },
  { value: 'saved', label: activityLabels.saved },
];

/** 주소에 실려 온 거르개. 모르는 값이 오면 전체로 되돌립니다. */
function parseFilter(value: string | null) {
  return value && filters.some((item) => item.value === value) ? value : ALL;
}

export function RecentActivityPage() {
  const openDetail = useTrendDetailLink();
  // 활동 화면은 목록이 곧 본문이라, 알림함과 달리 열자마자 받아 옵니다.
  const notificationsQuery = useNotifications(true);
  const savedTrendsQuery = useSavedTrends();
  const unreadCountQuery = useUnreadNotificationCount();
  const markAsRead = useMarkNotificationAsRead();
  const markAllAsRead = useMarkAllNotificationsAsRead();
  /*
   * 거르개를 주소에 싣습니다. 마이페이지의 알림 칸이 급등만 추린 목록으로 곧장 보낼 수 있어야
   * 하고, 뒤로 가기로 돌아왔을 때도 보던 갈래가 남습니다.
   */
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = parseFilter(searchParams.get('kind'));

  const notifications = useMemo(
    () => notificationsQuery.data?.pages.flatMap((page) => page.content) ?? [],
    [notificationsQuery.data],
  );
  // 두 목록 모두 새 배열을 만들어 돌려주므로, 합치기 전에 각각 붙잡아 둬야 매 렌더마다 다시 세우지 않습니다.
  const savedTrends = useMemo(() => savedTrendsQuery.data?.trends ?? [], [savedTrendsQuery.data]);
  const activities = useMemo(() => buildActivities(notifications, savedTrends), [notifications, savedTrends]);
  const shown = filter === ALL ? activities : activities.filter((activity) => activity.kind === filter);
  const groups = groupByDate(shown);

  const loading = notificationsQuery.isLoading || savedTrendsQuery.isLoading;
  const failed = notificationsQuery.isError && savedTrendsQuery.isError;

  const icons: Record<ActivityKind, typeof SurgeIcon> = { surge: SurgeIcon, saved: BookmarkIcon };
  const unreadCount = unreadCountQuery.data ?? 0;

  /*
   * 알림을 열면 읽음으로 바꿉니다. 읽음 처리가 실패해도 트렌드로 가는 길은 막지 않습니다.
   * 알림함(NotificationBell)과 같은 규칙입니다.
   */
  const openActivity = (notificationId: number | undefined, unread: boolean) => {
    if (unread && notificationId !== undefined) markAsRead.mutate(notificationId);
  };

  return (
    <MyPageScreen width="lg">
      <MyPageCrumb current="최근 활동" />

      <div className="mypage-head mypage-head--split">
        <h1>최근 활동</h1>
        <div className="mypage-head-tools">
          <span className="mypage-total">총 {shown.length}건</span>
          <button
            type="button"
            className="mypage-read-all"
            disabled={unreadCount === 0 || markAllAsRead.isPending}
            onClick={() => markAllAsRead.mutate()}
          >
            {markAllAsRead.isPending ? '읽음으로 바꾸는 중…' : `모두 읽음${unreadCount > 0 ? ` (${unreadCount})` : ''}`}
          </button>
        </div>
      </div>

      {/*
        * 활동 기록을 따로 쌓아 두는 API가 없어, 시각이 남는 두 가지만 모아 세웁니다.
        * 목록에 관심 키워드 등록이 없는 것을 빠뜨린 것으로 읽지 않도록 밝힙니다.
        */}
      <MyPageNotice>
        받은 알림과 트렌드를 담은 기록을 모아 보여 줍니다. 관심 키워드를 등록한 시각은 서버가 남기지 않아 아직 담지 못했습니다.
      </MyPageNotice>

      <div className="mypage-tabs">
        {filters.map((item) => (
          <button
            key={item.value}
            type="button"
            aria-pressed={filter === item.value}
            className={`mypage-tab${filter === item.value ? ' is-active' : ''}`}
            onClick={() => setSearchParams(item.value === ALL ? {} : { kind: item.value }, { replace: true })}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading && <div className="trendin-state" aria-label="불러오는 중"><span /><span /><span /></div>}

      {failed && (
        <div className="trendin-state is-error" role="alert">
          <p>최근 활동을 불러오지 못했습니다.</p>
          <button type="button" onClick={() => { void notificationsQuery.refetch(); void savedTrendsQuery.refetch(); }}>다시 시도</button>
        </div>
      )}

      {!loading && !failed && shown.length === 0 && (
        <p className="mypage-empty">아직 쌓인 활동이 없습니다. 관심 키워드를 등록해 두면 트렌드에 오를 때 알려 드립니다.</p>
      )}

      {groups.map((group) => (
        <section className="mypage-activity-group" key={group.date}>
          <h2>{formatActivityDate(group.date)}</h2>
          <ul>
            {group.items.map((activity) => {
              const Icon = icons[activity.kind];
              return (
                <li key={activity.id} className={activity.unread ? 'is-unread' : ''}>
                  <Link
                    className="mypage-activity"
                    {...openDetail(activity.trendId)}
                    onClick={() => openActivity(activity.notificationId, activity.unread)}
                  >
                    <span className={`mypage-activity-icon mypage-activity-icon--${activity.kind}`}><Icon size={14} /></span>
                    <span className="mypage-activity-text">
                      <strong>{activity.text}</strong>
                      <small>{activity.time}</small>
                    </span>
                    <span className={`mypage-activity-tag mypage-activity-tag--${activity.kind}`}>{activityLabels[activity.kind]}</span>
                    <ChevronIcon />
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {/*
        * 담은 트렌드는 한 번에 다 오고 알림만 쪽으로 나뉘어 옵니다. 그래서 더 받는 것은
        * 언제나 알림 쪽이고, 목록 아래쪽만 길어집니다.
        */}
      {notificationsQuery.hasNextPage && (
        <div className="mypage-more">
          <button
            type="button"
            className="mypage-btn mypage-btn--ghost"
            disabled={notificationsQuery.isFetchingNextPage}
            onClick={() => void notificationsQuery.fetchNextPage()}
          >
            {notificationsQuery.isFetchingNextPage ? '불러오는 중…' : '이전 활동 더 보기'}
          </button>
        </div>
      )}
    </MyPageScreen>
  );
}
