import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ToggleSwitch } from '../../components/common/ToggleSwitch';
import { showToast } from '../../components/common/toast';
import { MyPageCard, MyPageCrumb, MyPageNotice, MyPageRow, MyPageScreen } from '../../features/myPage/components/MyPageShell';
import { MailIcon, MoonIcon, ReportIcon, SurgeIcon } from '../../features/myPage/components/myPageIcons';
import { useNotificationSettings } from '../../features/notification/hooks/useNotificationSettings';
import type {
  EmailAlertKey,
  NotificationSettings,
  ReportAlertKey,
  TrendAlertKey,
} from '../../features/notification/types/notificationSettings';

/* 화면에 세울 줄. 순서와 설명 글은 시안 그대로입니다. */
const trendRows: { key: TrendAlertKey; title: string; desc: string }[] = [
  { key: 'surge', title: '키워드 급등 알림', desc: '관심 키워드 검색량이 급등하면 즉시 알림' },
  { key: 'plunge', title: '키워드 급락 알림', desc: '관심 키워드 검색량이 급락하면 알림' },
  { key: 'discovered', title: '신규 트렌드 발견', desc: '새로운 트렌드가 감지되면 알림' },
  { key: 'turning', title: '트렌드 전환점 알림', desc: '트렌드가 상승·하락으로 돌아설 때 알림' },
];

const reportRows: { key: ReportAlertKey; title: string; desc: string }[] = [
  { key: 'monthly', title: '월간 리포트 완성', desc: '매월 1일 월간 분석 리포트 알림' },
  { key: 'custom', title: '맞춤 리포트 완료', desc: '요청한 맞춤 리포트 생성 완료 시 알림' },
];

const emailRows: { key: EmailAlertKey; title: string; desc: string }[] = [
  { key: 'marketing', title: '마케팅 · 이벤트', desc: 'TrendIn 신규 기능 및 이벤트 소식' },
  { key: 'system', title: '시스템 공지', desc: '서비스 점검, 업데이트 등 시스템 알림' },
];

export function NotificationSettingsPage() {
  const [saved, save] = useNotificationSettings();
  /*
   * 시안에 저장 단추가 있어, 켜고 끈 것은 먼저 이 초안에만 담고 저장할 때 한 번에 씁니다.
   * 스위치를 누르는 즉시 쓰면 잘못 눌렀을 때 되돌릴 자리가 없습니다.
   */
  const [draft, setDraft] = useState<NotificationSettings>(saved);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  /* 전체 알림을 끄면 아래 항목을 잠급니다. 켠 자리는 지우지 않아서 다시 켜면 그대로 돌아옵니다. */
  const locked = !draft.master;

  const setGroup = <G extends 'trend' | 'report' | 'email'>(group: G, key: keyof NotificationSettings[G], on: boolean) => {
    setDraft((current) => ({ ...current, [group]: { ...current[group], [key]: on } }));
  };

  return (
    <MyPageScreen width="md">
      <MyPageCrumb current="알림 설정" />

      <div className="mypage-head mypage-head--split">
        <div>
          <h1>알림 설정</h1>
          <p>알림 수신 방법과 항목을 세부적으로 관리하세요.</p>
        </div>
        <div className="mypage-master">
          <span>전체 알림</span>
          <ToggleSwitch
            size="md"
            checked={draft.master}
            label="전체 알림"
            onChange={(on) => setDraft((current) => ({ ...current, master: on }))}
          />
        </div>
      </div>

      {/*
        * 백엔드에는 알림 설정을 받아 두는 API가 아직 없습니다. 저장한 값이 어디에 남는지
        * 밝히지 않으면, 껐는데 알림이 오는 것을 고장으로 읽게 됩니다.
        */}
      <MyPageNotice>
        고른 값은 아직 <strong>이 기기에만</strong> 저장됩니다. 서버가 알림 설정을 받기 시작하면 그대로 옮겨 갑니다.
        지금 나가는 알림은 관심 키워드가 트렌드에 오를 때 한 가지입니다.
      </MyPageNotice>

      <MyPageCard title="트렌드 알림" tone="rose" icon={<SurgeIcon />}>
        <div className="mypage-rows">
          {trendRows.map((row) => (
            <MyPageRow key={row.key} title={row.title} description={row.desc}>
              <ToggleSwitch
                checked={draft.trend[row.key] && !locked}
                disabled={locked}
                label={row.title}
                onChange={(on) => setGroup('trend', row.key, on)}
              />
            </MyPageRow>
          ))}
        </div>
      </MyPageCard>

      <MyPageCard title="리포트 알림" tone="amber" icon={<ReportIcon />}>
        <div className="mypage-rows">
          {reportRows.map((row) => (
            <MyPageRow key={row.key} title={row.title} description={row.desc}>
              <ToggleSwitch
                checked={draft.report[row.key] && !locked}
                disabled={locked}
                label={row.title}
                onChange={(on) => setGroup('report', row.key, on)}
              />
            </MyPageRow>
          ))}
        </div>
      </MyPageCard>

      <MyPageCard title="이메일 알림" tone="blue" icon={<MailIcon />}>
        <div className="mypage-rows">
          {emailRows.map((row) => (
            <MyPageRow key={row.key} title={row.title} description={row.desc}>
              <ToggleSwitch
                checked={draft.email[row.key] && !locked}
                disabled={locked}
                label={row.title}
                onChange={(on) => setGroup('email', row.key, on)}
              />
            </MyPageRow>
          ))}
        </div>
      </MyPageCard>

      <MyPageCard title="방해 금지 시간" tone="slate" icon={<MoonIcon />}>
        <div className="mypage-rows">
          <MyPageRow title="방해 금지 모드" description="설정한 시간 동안 모든 알림을 받지 않습니다.">
            <ToggleSwitch
              checked={draft.quiet.enabled && !locked}
              disabled={locked}
              label="방해 금지 모드"
              onChange={(on) => setDraft((current) => ({ ...current, quiet: { ...current.quiet, enabled: on } }))}
            />
          </MyPageRow>
        </div>
        {draft.quiet.enabled && !locked && (
          <div className="mypage-quiet">
            <label>
              <span>시작 시간</span>
              <input
                type="time"
                value={draft.quiet.start}
                onChange={(event) => setDraft((current) => ({ ...current, quiet: { ...current.quiet, start: event.target.value } }))}
              />
            </label>
            <span className="mypage-quiet-tilde" aria-hidden="true">~</span>
            <label>
              <span>종료 시간</span>
              <input
                type="time"
                value={draft.quiet.end}
                onChange={(event) => setDraft((current) => ({ ...current, quiet: { ...current.quiet, end: event.target.value } }))}
              />
            </label>
          </div>
        )}
      </MyPageCard>

      <div className="mypage-actions">
        <Link className="mypage-btn mypage-btn--ghost" to="/mypage">돌아가기</Link>
        <button
          type="button"
          className="mypage-btn mypage-btn--primary"
          disabled={!dirty}
          onClick={() => {
            save(() => draft);
            showToast({ message: '알림 설정을 저장했습니다.', type: 'success' });
          }}
        >
          저장
        </button>
      </div>
    </MyPageScreen>
  );
}
