import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ToggleSwitch } from '../../components/common/ToggleSwitch';
import { MyPageCard, MyPageRow, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import {
  BellIcon,
  BookmarkIcon,
  ChevronIcon,
  ClockIcon,
  DownloadIcon,
  GearIcon,
  GridIcon,
  LockIcon,
  SurgeIcon,
} from '../../features/myPage/components/myPageIcons';
import { activityLabels, buildActivities, formatActivityDate } from '../../features/myPage/activity';
import { useInterestKeywords } from '../../features/myPage/hooks/useInterestKeywords';
import { useMyProfile } from '../../features/myPage/hooks/useMyProfile';
import { useLogout } from '../../features/auth/hooks/useLogout';
import { useNotifications } from '../../features/notification/hooks/useNotifications';
import { useMarkNotificationAsRead } from '../../features/notification/hooks/useNotificationMutations';
import { useNotificationSettings } from '../../features/notification/hooks/useNotificationSettings';
import { useUnreadNotificationCount } from '../../features/notification/hooks/useUnreadNotificationCount';
import { useMyDomains } from '../../features/onboarding/hooks/useMyDomains';
import { useSavedTrends } from '../../features/savedTrend/hooks/useSavedTrends';
import { useTrendDetailLink } from '../../features/trend/trendDetailLink';
import type { ActivityKind } from '../../features/myPage/activity';
import type { NotificationSettings } from '../../features/notification/types/notificationSettings';

/** 요약 자리에는 최근 다섯 줄만 세웁니다. 나머지는 최근 활동 화면이 맡습니다. */
const ACTIVITY_PREVIEW = 5;

/** 이메일을 모르는 소셜 계정도 있어서, 머리글자를 못 뽑으면 기본 글자를 씁니다. */
function initialOf(nickname: string, email: string) {
  return (nickname.trim()[0] ?? email.trim()[0] ?? 'T').toUpperCase();
}

/*
 * 숫자 한 칸. 그 숫자를 보거나 손볼 화면이 있으면 칸 전체가 그리로 가는 링크가 되고,
 * 모서리에 꺾쇠가 섭니다 — 계정 설정 줄들과 같은 표시입니다. 칸마다 '관리'·'보기'처럼
 * 다른 말을 달면 같은 일을 하는 자리가 넷 다 달라 보입니다.
 */
function StatCard({ tone, icon, label, value, unit, to, accent = false }: {
  tone: string;
  icon: ReactNode;
  label: string;
  value: number | string;
  unit?: string;
  to?: string;
  accent?: boolean;
}) {
  const body = (
    <>
      <span className="mypage-stat-head">
        <span className={`mypage-card-icon mypage-card-icon--${tone}`}>{icon}</span>
        <span className="mypage-stat-label">{label}</span>
        {to && <span className="mypage-stat-go"><ChevronIcon /></span>}
      </span>
      <strong className={`mypage-stat-value${accent ? ' is-accent' : ''}`}>
        {value}{unit && <small>{unit}</small>}
      </strong>
    </>
  );

  if (!to) return <div className="mypage-stat">{body}</div>;
  return <Link className="mypage-stat is-link" to={to}>{body}</Link>;
}

/*
 * 요약 자리에 세울 알림 스위치입니다. 전체 관리 화면과 같은 값을 보되, 자주 여닫는 것만
 * 꺼내 둡니다. 여기서는 누르는 즉시 저장합니다 — 저장 단추를 둘 자리가 없어서입니다.
 */
interface NotificationRow {
  title: string;
  desc: string;
  read: (settings: NotificationSettings) => boolean;
  write: (settings: NotificationSettings, on: boolean) => NotificationSettings;
}

const notificationRows: NotificationRow[] = [
  {
    title: '트렌드 급등 알림',
    desc: '관심 키워드가 급등하면 즉시 알림',
    read: (settings) => settings.trend.surge,
    write: (settings, on) => ({ ...settings, trend: { ...settings.trend, surge: on } }),
  },
  {
    title: '신규 트렌드 발견',
    desc: '새로운 트렌드가 감지되면 알림',
    read: (settings) => settings.trend.discovered,
    write: (settings, on) => ({ ...settings, trend: { ...settings.trend, discovered: on } }),
  },
];

const accountLinks: { to: string; icon: ReactNode; title: string; desc: string }[] = [
  { to: '/mypage/settings', icon: <LockIcon />, title: '비밀번호 변경', desc: '메일로 인증번호를 받아 다시 세우기' },
  { to: '/mypage/settings', icon: <DownloadIcon />, title: '데이터 내보내기', desc: '관심 키워드, 저장된 트렌드 내려받기' },
];

export function MyPage() {
  const navigate = useNavigate();
  const openDetail = useTrendDetailLink();
  const profileQuery = useMyProfile();
  const domainsQuery = useMyDomains(true);
  const keywordsQuery = useInterestKeywords();
  const savedTrendsQuery = useSavedTrends();
  const unreadCountQuery = useUnreadNotificationCount();
  const notificationsQuery = useNotifications(true);
  const [settings, updateSettings] = useNotificationSettings();
  const markAsRead = useMarkNotificationAsRead();
  const logoutMutation = useLogout();

  const profile = profileQuery.data;
  const notifications = useMemo(
    () => notificationsQuery.data?.pages.flatMap((page) => page.content) ?? [],
    [notificationsQuery.data],
  );
  const savedTrends = useMemo(() => savedTrendsQuery.data?.trends ?? [], [savedTrendsQuery.data]);
  const activities = useMemo(
    () => buildActivities(notifications, savedTrends).slice(0, ACTIVITY_PREVIEW),
    [notifications, savedTrends],
  );

  const icons: Record<ActivityKind, typeof SurgeIcon> = { surge: SurgeIcon, saved: BookmarkIcon };

  const signOut = async () => {
    await logoutMutation.mutateAsync();
    navigate('/', { replace: true });
  };

  return (
    <MyPageScreen width="wide">
      <div className="mypage-head mypage-head--top trendin-page-heading">
        <p className="mypage-eyebrow">내 계정과 활동을 한눈에</p>
        <h1>마이페이지</h1>
      </div>

      {profileQuery.isError && (
        <div className="trendin-state is-error" role="alert">
          <p>프로필을 불러오지 못했습니다.</p>
          <button type="button" onClick={() => profileQuery.refetch()}>다시 시도</button>
        </div>
      )}

      <section className="mypage-overview">
        <div className="mypage-card mypage-profile">
          <span className="mypage-avatar" aria-hidden="true">
            {profile ? initialOf(profile.nickname, profile.email) : 'T'}
          </span>
          <p className="mypage-profile-name">{profile?.nickname ?? '…'}</p>
          {/* 소셜로 들어온 계정은 이메일을 모를 수 있습니다. 빈 줄 대신 그 사정을 적습니다. */}
          <p className="mypage-profile-email">{profile ? (profile.email || '연결된 소셜 계정') : ''}</p>
          <div className="mypage-profile-actions">
            <Link className="mypage-btn mypage-btn--ghost" to="/mypage/profile">프로필 편집</Link>
            <button
              type="button"
              className="mypage-btn mypage-btn--dark"
              disabled={logoutMutation.isPending}
              onClick={() => void signOut()}
            >
              {logoutMutation.isPending ? '로그아웃 중…' : '로그아웃'}
            </button>
          </div>
        </div>

        {/*
          * 시안의 여섯 칸 가운데 보드·최근 접속은 서버가 세어 주지 않고, 생성 리포트는 기능째 걷어냈습니다.
          * 빈 칸을 0으로 채우면 없는 것을 있다고 말하게 되므로, 셀 수 있는 넷만 세웁니다.
          */}
        <div className="mypage-stats">
          <StatCard
            tone="indigo"
            icon={<BookmarkIcon />}
            label="관심 키워드"
            value={keywordsQuery.data?.length ?? 0}
            unit="개"
            to="/interest-keywords"
          />
          <StatCard
            tone="blue"
            icon={<GridIcon />}
            label="관심 분야"
            value={domainsQuery.data?.length ?? 0}
            unit="곳"
            to="/mypage/profile"
          />
          <StatCard
            tone="emerald"
            icon={<BellIcon />}
            label="안 읽은 알림"
            value={unreadCountQuery.data ?? 0}
            unit="개"
            accent
            to="/mypage/activity?kind=surge"
          />
          <StatCard
            tone="rose"
            icon={<BookmarkIcon />}
            label="저장된 트렌드"
            value={savedTrends.length}
            unit="개"
            to="/saved"
          />
        </div>
      </section>

      <section className="mypage-columns">
        <MyPageCard
          title="알림 설정"
          tone="indigo"
          icon={<BellIcon />}
          action={<Link className="mypage-card-link" to="/mypage/notifications">전체 관리 →</Link>}
        >
          <div className="mypage-rows">
            {notificationRows.map((row) => (
              <MyPageRow key={row.title} title={row.title} description={row.desc}>
                <ToggleSwitch
                  checked={settings.master && row.read(settings)}
                  disabled={!settings.master}
                  label={row.title}
                  onChange={(on) => updateSettings((current) => row.write(current, on))}
                />
              </MyPageRow>
            ))}
          </div>
        </MyPageCard>

        <MyPageCard title="계정 설정" tone="slate" icon={<GearIcon />}>
          <div className="mypage-rows">
            {accountLinks.map((link) => (
              <Link className="mypage-link-row" key={link.title} to={link.to}>
                <span className="mypage-link-icon">{link.icon}</span>
                <span className="mypage-row-text">
                  <span className="mypage-row-title">{link.title}</span>
                  <span className="mypage-row-desc">{link.desc}</span>
                </span>
                <ChevronIcon />
              </Link>
            ))}
          </div>
        </MyPageCard>
      </section>

      <MyPageCard
        title="최근 활동"
        tone="amber"
        icon={<ClockIcon />}
        action={<Link className="mypage-card-link" to="/mypage/activity">전체 보기 →</Link>}
      >
        {activities.length === 0 && (
          <p className="mypage-empty">아직 쌓인 활동이 없습니다. 관심 키워드를 등록해 두면 트렌드에 오를 때 알려 드립니다.</p>
        )}
        {activities.length > 0 && (
          <ul className="mypage-preview">
            {activities.map((activity) => {
              const Icon = icons[activity.kind];
              return (
                <li key={activity.id} className={activity.unread ? 'is-unread' : ''}>
                  <Link
                    className="mypage-activity"
                    {...openDetail(activity.trendId)}
                    /* 요약에서 열어도 읽음으로 바뀝니다. 최근 활동 화면과 같은 규칙입니다. */
                    onClick={() => { if (activity.unread && activity.notificationId !== undefined) markAsRead.mutate(activity.notificationId); }}
                  >
                    <span className={`mypage-activity-icon mypage-activity-icon--${activity.kind}`}><Icon size={14} /></span>
                    <span className="mypage-activity-text">
                      <strong>{activity.text}</strong>
                      <small>{formatActivityDate(activity.date)} {activity.time}</small>
                    </span>
                    <span className={`mypage-activity-tag mypage-activity-tag--${activity.kind}`}>{activityLabels[activity.kind]}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </MyPageCard>
    </MyPageScreen>
  );
}
